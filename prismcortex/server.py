"""PrismCortex memory service — multi-tenant, RBAC, observability, enterprise APIs."""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import time
from collections import deque
from threading import Lock, Semaphore
from typing import Any, Callable, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import (
    ROLE_ADMIN,
    ROLE_FORGET,
    ROLE_READ,
    ROLE_WRITE,
    AuthContext,
    auth_required,
    authenticate,
)
from .engine import Memory
from .labels import aliases_snapshot, load_aliases, register_alias, save_aliases
from .policy import PolicyEngine
from .server_helpers import CountingGemini, rate_limiter_from_env, read_executor, write_executor
from .tenant import TenantMemoryManager
from .tracing import current_trace, start_trace, trace_enabled, traced

DATA_DIR = os.environ.get("PRISMCORTEX_DATA", ".prismcortex_data")
os.makedirs(DATA_DIR, exist_ok=True)

logger = logging.getLogger("prismcortex")
logger.setLevel(logging.INFO)
_fmt = logging.Formatter("%(message)s")
_sh = logging.StreamHandler()
_sh.setFormatter(_fmt)
logger.addHandler(_sh)
_fh = logging.FileHandler(os.path.join(DATA_DIR, "server.jsonl"))
_fh.setFormatter(_fmt)
logger.addHandler(_fh)


def log_event(**fields) -> None:
    tr = current_trace()
    if tr:
        fields["trace_id"] = tr.trace_id
    fields["ts"] = round(time.time(), 4)
    logger.info(json.dumps(fields, separators=(",", ":")))


class Metrics:
    def __init__(self) -> None:
        self.started = time.time()
        self.counts = {"digest": 0, "recall": 0, "sleep": 0, "errors": 0, "rate_limited": 0}
        self.cache_hits = 0
        self.cache_misses = 0
        self.raw_bytes = 0
        self._lat = {"digest": deque(maxlen=5000), "recall": deque(maxlen=5000)}
        self._lock = Lock()

    def record(self, op: str, ms: float) -> None:
        with self._lock:
            if op in self._lat:
                self._lat[op].append(ms)

    def reset(self) -> None:
        with self._lock:
            self.started = time.time()
            self.counts = {"digest": 0, "recall": 0, "sleep": 0, "errors": 0, "rate_limited": 0}
            self.cache_hits = 0
            self.cache_misses = 0
            self.raw_bytes = 0
            for d in self._lat.values():
                d.clear()

    @staticmethod
    def _pct(vals, p):
        if not vals:
            return None
        s = sorted(vals)
        i = min(len(s) - 1, int(round((p / 100) * (len(s) - 1))))
        return round(s[i], 2)

    def snapshot(self, gemini_calls: int, backend: str, graph_version: int, *, staging: int = 0, conflicts: int = 0) -> dict:
        with self._lock:
            lat = {op: {"n": len(v), "p50": self._pct(v, 50), "p95": self._pct(v, 95), "p99": self._pct(v, 99)} for op, v in self._lat.items()}
        total = self.cache_hits + self.cache_misses
        return {
            "backend": backend,
            "uptime_s": round(time.time() - self.started, 1),
            "counts": dict(self.counts),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": round(self.cache_hits / total, 4) if total else None,
            "gemini_calls": gemini_calls,
            "graph_version": graph_version,
            "staging_pending": staging,
            "conflicts_open": conflicts,
            "latency_ms": lat,
        }


metrics = Metrics()
_backend = os.environ.get("PRISMCORTEX_BACKEND", "lite")
_use_ann = os.environ.get("PRISMCORTEX_USE_ANN", "1") != "0"
_tenant_mgr: Optional[TenantMemoryManager] = None
_policy = PolicyEngine(DATA_DIR)
_rate_limiter = rate_limiter_from_env()
_digest_sem = Semaphore(int(os.environ.get("PRISMCORTEX_MAX_CONCURRENT_DIGEST", "16")))
_build_lock = Lock()


async def _run_read(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(read_executor(), lambda: fn(*args, **kwargs))


async def _run_write(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(write_executor(), lambda: fn(*args, **kwargs))

# Back-compat for tests: set _memory directly to bypass tenant manager
_memory: Optional[Memory] = None
_llm: Optional[CountingGemini] = None

API_KEY = os.environ.get("PRISMCORTEX_API_KEY")
_OPEN_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/docs/oauth2-redirect", "/console", "/console/"}
if not auth_required():
    logger.warning(json.dumps({"event": "auth_disabled", "warn": "No API keys configured — UNAUTHENTICATED (dev only)"}))

_alias_path = os.path.join(DATA_DIR, "aliases.json")
if os.path.isfile(_alias_path):
    load_aliases(_alias_path)


def _tenant_mgr_instance() -> TenantMemoryManager:
    global _tenant_mgr
    if _tenant_mgr is None:
        with _build_lock:
            if _tenant_mgr is None:
                _tenant_mgr = TenantMemoryManager(DATA_DIR, _backend, use_ann=_use_ann)
    return _tenant_mgr


def get_memory(auth: Optional[AuthContext] = None) -> tuple[Memory, Optional[CountingGemini]]:
    global _memory, _llm
    if _memory is not None:
        return _memory, _llm
    tenant = auth.tenant_id if auth else "default"
    region = auth.region if auth else os.environ.get("PRISMCORTEX_REGION", "default")
    mem, llm = _tenant_mgr_instance().get(tenant, region)
    log_event(event="memory_built", tenant=tenant, region=region, backend=_backend)
    return mem, llm


def _auth_ctx(request: Request) -> Optional[AuthContext]:
    if not auth_required():
        return AuthContext()
    token = request.headers.get("x-api-key") or _bearer(request.headers.get("authorization"))
    return authenticate(token)


def _bearer(auth: Optional[str]) -> Optional[str]:
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1]
    return None


def _deny(msg: str, code: int = 403) -> JSONResponse:
    return JSONResponse({"detail": msg}, status_code=code)


app = FastAPI(title="PrismCortex", version="0.2.1")
_static = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static):
    app.mount("/console", StaticFiles(directory=_static, html=True), name="console")


@app.middleware("http")
async def _middleware(request: Request, call_next):
    if trace_enabled() and request.url.path not in _OPEN_PATHS:
        start_trace(request.headers.get("x-trace-id"))
    auth = _auth_ctx(request)
    if auth_required() and request.url.path not in _OPEN_PATHS:
        token = request.headers.get("x-api-key") or _bearer(request.headers.get("authorization"))
        if not auth:
            return JSONResponse({"detail": "invalid or missing API key"}, status_code=401)
        if _rate_limiter and not _rate_limiter.allow(token or request.client.host or "anon"):
            metrics.counts["rate_limited"] += 1
            return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
    request.state.auth = auth
    resp = await call_next(request)
    tr = current_trace()
    if tr and trace_enabled():
        log_event(event="trace", **tr.to_dict())
    return resp


class DigestBody(BaseModel):
    text: str = Field(max_length=100_000)
    source_id: Optional[str] = Field(default=None, max_length=256)
    agent_id: Optional[str] = Field(default=None, max_length=256)


class RecallBody(BaseModel):
    query: str = Field(max_length=8_000)


class ForgetBody(BaseModel):
    source_id: str


class AliasBody(BaseModel):
    canonical: str
    alias: str


class ResolveBody(BaseModel):
    subject: str
    relation: str
    chosen_value: str


class LegalHoldBody(BaseModel):
    source_id: str


@app.get("/health")
def health():
    mem, _ = get_memory(AuthContext()) if _memory or _tenant_mgr else (None, None)
    alerts = []
    staging = mem.staging.pending_count() if mem else 0
    if staging > int(os.environ.get("PRISMCORTEX_STAGING_WARN", "50")):
        alerts.append({"level": "warn", "msg": f"staging backlog={staging}"})
    if metrics.counts["errors"] > 10:
        alerts.append({"level": "warn", "msg": f"errors={metrics.counts['errors']}"})
    return {
        "ok": True,
        "version": "0.2.1",
        "backend": _backend,
        "auth": auth_required(),
        "multi_tenant": True,
        "ann": _use_ann,
        "alerts": alerts,
    }


@app.post("/digest")
async def digest(body: DigestBody, request: Request):
    auth: AuthContext = request.state.auth or AuthContext()
    if auth_required() and not auth.allows(ROLE_WRITE):
        return _deny("write role required")
    if not _digest_sem.acquire(blocking=False):
        metrics.counts["rate_limited"] += 1
        return JSONResponse({"detail": "digest backpressure — retry later"}, status_code=429)
    try:
        mem, _ = get_memory(auth)
        metrics.raw_bytes += len(body.text.encode("utf-8"))
        t0 = time.perf_counter()

        def work():
            with traced("digest"):
                return mem.digest(body.text, source_id=body.source_id, agent_id=body.agent_id)

        try:
            res = await _run_write(work)
        except Exception as exc:  # noqa: BLE001
            metrics.counts["errors"] += 1
            log_event(event="digest_error", error=str(exc)[:200])
            raise
        ms = (time.perf_counter() - t0) * 1000
        metrics.counts["digest"] += 1
        metrics.record("digest", ms)
        log_event(event="digest", tenant=auth.tenant_id, outcome=res.outcome.value, ms=round(ms, 2))
        return {"outcome": res.outcome.value, "band": res.band.value, "version": res.version.version, "ms": round(ms, 2)}
    finally:
        _digest_sem.release()


@app.post("/recall")
async def recall(body: RecallBody, request: Request):
    auth: AuthContext = request.state.auth or AuthContext()
    if auth_required() and not auth.allows(ROLE_READ):
        return _deny("read role required")
    mem, _ = get_memory(auth)
    t0 = time.perf_counter()

    def work():
        with traced("recall"):
            return mem.recall(body.query)

    res = await _run_read(work)
    ms = (time.perf_counter() - t0) * 1000
    metrics.counts["recall"] += 1
    metrics.record("recall", ms)
    metrics.cache_hits += int(res.cache_hit)
    metrics.cache_misses += int(not res.cache_hit)
    return {
        "answer": res.answer, "cache_hit": res.cache_hit, "subgraph_hash": res.subgraph_hash,
        "version": res.version, "confidence": res.confidence,
        "freshness": res.freshness.isoformat() if res.freshness else None,
        "node_ids": res.node_ids, "edge_ids": res.edge_ids, "ms": round(ms, 2),
    }


@app.post("/explain")
def explain(body: RecallBody, request: Request):
    auth: AuthContext = request.state.auth or AuthContext()
    if auth_required() and not auth.allows(ROLE_READ):
        return _deny("read role required")
    mem, _ = get_memory(auth)
    return mem.explain(body.query).model_dump(mode="json")


@app.post("/recall_at")
def recall_at(body: RecallBody, request: Request, at: Optional[str] = None):
    auth: AuthContext = request.state.auth or AuthContext()
    if auth_required() and not auth.allows(ROLE_READ):
        return _deny("read role required")
    mem, _ = get_memory(auth)
    res = mem.recall_at(body.query, at=at)
    return res.model_dump(mode="json")


@app.get("/replay_certificate")
def replay_certificate(query: str, request: Request):
    auth: AuthContext = request.state.auth or AuthContext()
    if auth_required() and not auth.allows(ROLE_READ):
        return _deny("read role required")
    mem, _ = get_memory(auth)
    return mem.replay_certificate(query)


@app.post("/forget")
def forget(body: ForgetBody, request: Request):
    auth: AuthContext = request.state.auth or AuthContext()
    if auth_required() and not auth.allows(ROLE_FORGET, ROLE_ADMIN):
        return _deny("forget/admin role required")
    ok, reason = _policy.can_forget(body.source_id)
    if not ok:
        return _deny(reason, 409)
    mem, _ = get_memory(auth)
    receipt = mem.forget(body.source_id)
    log_event(event="forget", tenant=auth.tenant_id, **receipt)
    return receipt


@app.get("/conflicts")
def conflicts(request: Request):
    auth: AuthContext = request.state.auth or AuthContext()
    if auth_required() and not auth.allows(ROLE_READ):
        return _deny("read role required")
    mem, _ = get_memory(auth)
    return {"conflicts": mem.conflicts()}


@app.post("/conflicts/resolve")
def resolve_conflict(body: ResolveBody, request: Request):
    auth: AuthContext = request.state.auth or AuthContext()
    if auth_required() and not auth.allows(ROLE_WRITE, ROLE_ADMIN):
        return _deny("write/admin role required")
    mem, _ = get_memory(auth)
    try:
        v = mem.resolve_conflict(body.subject, body.relation, body.chosen_value)
    except ValueError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=404)
    return {"version": v.version, "content_hash": v.content_hash}


@app.get("/aliases")
def list_aliases(request: Request):
    auth: AuthContext = request.state.auth or AuthContext()
    return {"aliases": aliases_snapshot(tenant_id=auth.tenant_id)}


@app.post("/aliases")
def add_alias(body: AliasBody, request: Request):
    auth: AuthContext = request.state.auth or AuthContext()
    if auth_required() and not auth.allows(ROLE_WRITE, ROLE_ADMIN):
        return _deny("write role required")
    register_alias(body.canonical, body.alias, tenant_id=auth.tenant_id)
    save_aliases(os.path.join(DATA_DIR, f"aliases_{auth.tenant_id}.json"), tenant_id=auth.tenant_id)
    return {"ok": True}


@app.post("/legal_hold")
def legal_hold(body: LegalHoldBody, request: Request):
    auth: AuthContext = request.state.auth or AuthContext()
    if auth_required() and not auth.allows(ROLE_ADMIN):
        return _deny("admin role required")
    _policy.add_legal_hold(body.source_id)
    return {"ok": True, "source_id": body.source_id}


@app.delete("/legal_hold/{source_id}")
def release_hold(source_id: str, request: Request):
    auth: AuthContext = request.state.auth or AuthContext()
    if auth_required() and not auth.allows(ROLE_ADMIN):
        return _deny("admin role required")
    _policy.remove_legal_hold(source_id)
    return {"ok": True}


@app.get("/policy")
def policy_snapshot(request: Request):
    auth: AuthContext = request.state.auth or AuthContext()
    if auth_required() and not auth.allows(ROLE_READ, ROLE_ADMIN):
        return _deny("read role required")
    return _policy.snapshot()


@app.get("/tombstones")
def tombstones(request: Request):
    auth: AuthContext = request.state.auth or AuthContext()
    mem, _ = get_memory(auth)
    return {"tombstones": mem.store.tombstones() if hasattr(mem.store, "tombstones") else []}


@app.post("/sleep")
async def sleep(request: Request):
    auth: AuthContext = request.state.auth or AuthContext()
    if auth_required() and not auth.allows(ROLE_WRITE):
        return _deny("write role required")
    mem, _ = get_memory(auth)
    n = await _run_write(mem.sleep)
    metrics.counts["sleep"] += 1
    log_event(event="sleep", consolidated=n)
    return {"consolidated": n}


@app.get("/audit")
def audit(request: Request, at: Optional[str] = None):
    auth: AuthContext = request.state.auth or AuthContext()
    mem, _ = get_memory(auth)
    edges = mem.store.all_edges() if hasattr(mem.store, "all_edges") else []
    if at:
        from datetime import datetime, timezone
        ts = datetime.fromisoformat(at.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        valid = []
        for e in edges:
            vf = e.valid_from.replace(tzinfo=timezone.utc) if e.valid_from.tzinfo is None else e.valid_from
            vt = e.valid_to.replace(tzinfo=timezone.utc) if e.valid_to and e.valid_to.tzinfo is None else e.valid_to
            if vf <= ts and (vt is None or ts < vt):
                valid.append(e)
        return {"at": at, "edges_valid": len(valid), "total_edges": len(edges)}
    superseded = [e for e in edges if e.valid_to is not None]
    return {"total_edges": len(edges), "current": sum(1 for e in edges if e.valid_to is None), "superseded_retained": len(superseded)}


@app.get("/memory_stats")
def memory_stats(request: Request):
    auth: AuthContext = request.state.auth or AuthContext()
    mem, _ = get_memory(auth)
    nodes = mem.store.all_nodes() if hasattr(mem.store, "all_nodes") else []
    edges = [e for e in mem.store.all_edges() if e.valid_to is None] if hasattr(mem.store, "all_edges") else []
    id2label = {n.id: n.label for n in nodes}
    gist = json.dumps({"nodes": [{"label": n.label, "kind": n.kind} for n in nodes],
                       "edges": [{"s": id2label.get(e.src), "r": e.relation, "d": id2label.get(e.dst)} for e in edges]}, separators=(",", ":"))
    dim = len(nodes[0].embedding) if nodes and nodes[0].embedding else 0
    gist_bytes = len(gist.encode("utf-8"))
    index_bytes = len(nodes) * dim * 4
    raw = metrics.raw_bytes
    return {
        "tenant": auth.tenant_id, "region": auth.region,
        "raw_bytes_ingested": raw, "gist_bytes": gist_bytes, "index_bytes_est": index_bytes,
        "graph_nodes": len(nodes), "graph_current_edges": len(edges),
        "compression_ratio_gist": round(raw / gist_bytes, 2) if gist_bytes else None,
        "ann_enabled": getattr(mem.store, "tenant_id", None) is not None and _use_ann,
    }


@app.get("/metrics")
def get_metrics(request: Request):
    auth: AuthContext = request.state.auth or AuthContext()
    if auth_required() and not auth.allows(ROLE_READ):
        return _deny("read role required")
    mem, llm = (_memory, _llm) if _memory is not None else (None, None)
    if mem is None and _tenant_mgr is not None:
        mem, llm = _tenant_mgr.peek(auth.tenant_id, auth.region)
    gv = mem.store.version().version if mem else 0
    staging = mem.staging.pending_count() if mem else 0
    conflicts = len(mem.conflicts()) if mem else 0
    return metrics.snapshot(gemini_calls=(llm.calls if llm else 0), backend=_backend,
                            graph_version=gv, staging=staging, conflicts=conflicts)


@app.get("/dashboard")
def dashboard(request: Request):
    """Ops snapshot for monitoring (cache, staging, conflicts, errors)."""
    auth: AuthContext = request.state.auth or AuthContext()
    if auth_required() and not auth.allows(ROLE_READ):
        return _deny("read role required")
    m = get_metrics(request)
    if isinstance(m, JSONResponse):
        return m
    return {"health": health(), "metrics": m, "policy": _policy.snapshot()}


@app.post("/reset")
def reset(request: Request):
    auth: AuthContext = request.state.auth or AuthContext()
    if auth_required() and not auth.allows(ROLE_ADMIN):
        return _deny("admin role required")
    global _memory, _llm
    if _memory is not None:
        _memory = None
        _llm = None
    else:
        _tenant_mgr_instance().reset(auth.tenant_id, auth.region)
    metrics.reset()
    log_event(event="reset", tenant=auth.tenant_id)
    return {"ok": True}
