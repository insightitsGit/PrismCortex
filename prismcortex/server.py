"""PrismCortex memory service — the self-contained engine, made network-reachable.

One container running this IS the whole memory: engine + bitemporal graph + PrismLib
cache + real Gemini, all in-process. A second agent/benchmark container connects over
HTTP. No external datastore — PrismLib is the cache, inside.

Run:  uvicorn prismcortex.server:app --host 0.0.0.0 --port 8080
Env:  GEMINI_API_KEY (required for digest/recall)  ·  PRISMCORTEX_BACKEND=lite|prism
      PRISMCORTEX_DATA=/data  (where structured logs + cache are written)
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections import deque
from threading import Lock
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from .engine import Memory

# --------------------------------------------------------------------------- #
# structured JSON logging → stdout + (if PRISMCORTEX_DATA set) a file
# --------------------------------------------------------------------------- #
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
    fields["ts"] = round(time.time(), 4)
    logger.info(json.dumps(fields, separators=(",", ":")))


# --------------------------------------------------------------------------- #
# metrics
# --------------------------------------------------------------------------- #
class Metrics:
    def __init__(self) -> None:
        self.started = time.time()
        self.counts = {"digest": 0, "recall": 0, "sleep": 0, "errors": 0}
        self.cache_hits = 0
        self.cache_misses = 0
        self.raw_bytes = 0  # total bytes ingested = what an append-log would store
        self._lat = {"digest": deque(maxlen=5000), "recall": deque(maxlen=5000)}
        self._lock = Lock()

    def record(self, op: str, ms: float) -> None:
        with self._lock:
            if op in self._lat:
                self._lat[op].append(ms)

    def reset(self) -> None:
        with self._lock:
            self.started = time.time()
            self.counts = {"digest": 0, "recall": 0, "sleep": 0, "errors": 0}
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

    def snapshot(self, gemini_calls: int, backend: str, graph_version: int) -> dict:
        with self._lock:
            lat = {
                op: {
                    "n": len(v),
                    "p50": self._pct(v, 50),
                    "p95": self._pct(v, 95),
                    "p99": self._pct(v, 99),
                }
                for op, v in self._lat.items()
            }
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
            "latency_ms": lat,
        }


metrics = Metrics()

# --------------------------------------------------------------------------- #
# memory (built lazily so /health works before a key is needed)
# --------------------------------------------------------------------------- #
_memory: Optional[Memory] = None
_llm = None
_backend = os.environ.get("PRISMCORTEX_BACKEND", "lite")
_generation = 0  # bumped on /reset so the durable cache + resonance state start fresh
_build_lock = Lock()


class _CountingGemini:
    """Wraps the real GeminiClient and counts model calls (for cost metrics)."""

    def __init__(self, model: Optional[str] = None):
        from .llm.gemini import GeminiClient

        self._g = GeminiClient(model=model)
        self.calls = 0

    @property
    def model_id(self):
        return self._g.model_id

    def extract(self, text, context):
        self.calls += 1
        return self._g.extract(text, context)

    def render(self, query, subgraph):
        self.calls += 1
        return self._g.render(query, subgraph)


def get_memory() -> Memory:
    global _memory, _llm
    if _memory is not None:
        return _memory
    with _build_lock:
        if _memory is not None:
            return _memory
        from .adapters.reference import InMemoryGraphStore, InProcessMesh, ListStaging
        from .adapters.prism import PrismLibCache

        _llm = _CountingGemini(model=os.environ.get("PRISMCORTEX_MODEL"))
        gen = _generation
        cache = PrismLibCache(db_path=os.path.join(DATA_DIR, f"prismlib_cache_{gen}.db"))  # real PrismLib, inside

        if _backend == "prism":  # the full stack: real PrismLang + PrismResonance
            from .adapters.prism import PrismLangProjector, PrismResonanceAdapter

            projector = PrismLangProjector(tenant_id=os.environ.get("PRISMCORTEX_TENANT", "prismcortex"))
            resonance = PrismResonanceAdapter(
                embedding_dim=projector.dim,
                state_path=os.path.join(DATA_DIR, f"resonance_state_{gen}.db"),
                onnx_path=os.path.join(DATA_DIR, "resonance_engine.onnx"),  # compiled model is reused
            )
        else:  # lite: deterministic hashing embeddings + in-process resonance
            from .adapters.reference import HashingProjector, InProcessResonance

            projector = HashingProjector(dim=384)
            resonance = InProcessResonance()

        _memory = Memory(
            projector=projector,
            extractor=_llm,
            renderer=_llm,
            store=InMemoryGraphStore(),
            resonance=resonance,
            cache=cache,
            mesh=InProcessMesh(),
            staging=ListStaging(),
        )
        log_event(event="memory_built", backend=_backend, projector=type(projector).__name__, cache="prismlib.SQLiteStore")
        return _memory


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
app = FastAPI(title="PrismCortex", version="0.1.0")


class DigestBody(BaseModel):
    text: str
    source_id: Optional[str] = None
    agent_id: Optional[str] = None


class RecallBody(BaseModel):
    query: str


@app.get("/health")
def health():
    return {"ok": True, "version": "0.1.0", "backend": _backend, "memory_built": _memory is not None}


@app.post("/digest")
def digest(body: DigestBody):
    mem = get_memory()
    metrics.raw_bytes += len(body.text.encode("utf-8"))  # an append-log keeps every byte
    t0 = time.perf_counter()
    try:
        res = mem.digest(body.text, source_id=body.source_id, agent_id=body.agent_id)
    except Exception as exc:  # noqa: BLE001
        metrics.counts["errors"] += 1
        log_event(event="digest_error", error=str(exc)[:200])
        raise
    ms = (time.perf_counter() - t0) * 1000
    metrics.counts["digest"] += 1
    metrics.record("digest", ms)
    log_event(event="digest", outcome=res.outcome.value, band=res.band.value, version=res.version.version, ms=round(ms, 2))
    return {"outcome": res.outcome.value, "band": res.band.value, "version": res.version.version, "ms": round(ms, 2)}


@app.post("/recall")
def recall(body: RecallBody):
    mem = get_memory()
    t0 = time.perf_counter()
    try:
        res = mem.recall(body.query)
    except Exception as exc:  # noqa: BLE001
        metrics.counts["errors"] += 1
        log_event(event="recall_error", error=str(exc)[:200])
        raise
    ms = (time.perf_counter() - t0) * 1000
    metrics.counts["recall"] += 1
    metrics.record("recall", ms)
    if res.cache_hit:
        metrics.cache_hits += 1
    else:
        metrics.cache_misses += 1
    log_event(event="recall", cache_hit=res.cache_hit, version=res.version, hash=res.subgraph_hash[:16], ms=round(ms, 2))
    return {
        "answer": res.answer,
        "cache_hit": res.cache_hit,
        "subgraph_hash": res.subgraph_hash,
        "version": res.version,
        "confidence": res.confidence,
        "freshness": res.freshness.isoformat() if res.freshness else None,
        "node_ids": res.node_ids,
        "edge_ids": res.edge_ids,
        "ms": round(ms, 2),
    }


@app.post("/explain")
def explain(body: RecallBody):
    """The evidence trail behind an answer — facts, sources, confidence (audit feature)."""
    mem = get_memory()
    return mem.explain(body.query).model_dump(mode="json")


class ForgetBody(BaseModel):
    source_id: str


@app.post("/forget")
def forget(body: ForgetBody):
    """Right-to-be-forgotten: erase all facts from a source + clear the answer cache."""
    mem = get_memory()
    receipt = mem.forget(body.source_id)
    log_event(event="forget", **receipt)
    return receipt


@app.get("/conflicts")
def conflicts():
    """Contested facts the system would otherwise have to silently pick between."""
    mem = get_memory()
    return {"conflicts": mem.conflicts()}


@app.get("/tombstones")
def tombstones():
    """Audit log of erasures (content not retained, only the receipts)."""
    mem = get_memory()
    return {"tombstones": mem.store.tombstones() if hasattr(mem.store, "tombstones") else []}


@app.post("/sleep")
def sleep():
    mem = get_memory()
    n = mem.sleep()
    metrics.counts["sleep"] += 1
    log_event(event="sleep", consolidated=n)
    return {"consolidated": n}


@app.get("/audit")
def audit(src: Optional[str] = None, relation: Optional[str] = None):
    """Bitemporal proof: how many facts are superseded but retained (time-travel)."""
    mem = get_memory()
    edges = mem.store.all_edges() if hasattr(mem.store, "all_edges") else []
    superseded = [e for e in edges if e.valid_to is not None]
    return {
        "total_edges": len(edges),
        "current": sum(1 for e in edges if e.valid_to is None),
        "superseded_retained": len(superseded),
    }


@app.get("/memory_stats")
def memory_stats():
    """Memory savings: the gist graph vs the raw conversation an append-log would keep."""
    mem = get_memory()
    nodes = mem.store.all_nodes() if hasattr(mem.store, "all_nodes") else []
    edges = [e for e in mem.store.all_edges() if e.valid_to is None] if hasattr(mem.store, "all_edges") else []
    id2label = {n.id: n.label for n in nodes}
    # the gist = the semantic memory actually stored (labels + attributes + relations),
    # excluding embeddings, which are a rebuildable index, not stored knowledge.
    gist = json.dumps(
        {
            "nodes": [{"label": n.label, "kind": n.kind, "attributes": n.attributes} for n in nodes],
            "edges": [{"s": id2label.get(e.src, e.src), "r": e.relation, "d": id2label.get(e.dst, e.dst)} for e in edges],
        },
        separators=(",", ":"),
    )
    dim = len(nodes[0].embedding) if nodes and nodes[0].embedding else 0
    gist_bytes = len(gist.encode("utf-8"))
    index_bytes = len(nodes) * dim * 4  # float32 vectors (the ANN index footprint)
    raw = metrics.raw_bytes
    return {
        "raw_bytes_ingested": raw,
        "gist_bytes": gist_bytes,
        "index_bytes_est": index_bytes,
        "graph_nodes": len(nodes),
        "graph_current_edges": len(edges),
        "compression_ratio_gist": round(raw / gist_bytes, 2) if gist_bytes else None,
        "compression_ratio_with_index": round(raw / (gist_bytes + index_bytes), 2) if (gist_bytes + index_bytes) else None,
    }


@app.get("/metrics")
def get_metrics():
    mem = get_memory() if _memory is not None else None
    gv = mem.store.version().version if mem is not None else 0
    return metrics.snapshot(gemini_calls=(_llm.calls if _llm else 0), backend=_backend, graph_version=gv)


@app.post("/reset")
def reset():
    """Fresh memory + metrics + cache for a clean benchmark run."""
    global _memory, _llm, _generation
    with _build_lock:
        _generation += 1  # next get_memory() uses fresh cache + resonance state files
        try:  # release the old resonance engine's onnx/state handles cleanly
            if _memory is not None and hasattr(_memory.resonance, "shutdown"):
                _memory.resonance.shutdown()
        except Exception:  # noqa: BLE001
            pass
        _memory = None
        _llm = None
        metrics.reset()
    log_event(event="reset")
    return {"ok": True}
