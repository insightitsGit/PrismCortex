"""PrismCortex benchmark driver — the second container / second agent.

Connects to the memory service over the network and proves the product's claims with
real measurements (real Gemini behind the server, no mocks):

  INGEST          digest latency + salience-gate skips
  DETERMINISM     same query over the network → byte-identical answer + cache hits
  RECONSOLIDATION corrected fact changes the answer; old fact retained (time-travel)
  THROUGHPUT      concurrent cached recalls → rps + p50/p95/p99
  LOAD            split sustained load — recall burst, digest burst, mixed smoke
  COST            Gemini calls actually made vs recalls served

Results + logs are written under PRISMCORTEX_DATA and printed to stdout.
Env:  SERVER_URL (default http://localhost:8080)
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

SERVER = os.environ.get("SERVER_URL", "http://localhost:8080").rstrip("/")
APIKEY = os.environ.get("PRISMCORTEX_API_KEY")
_HEADERS = {"Content-Type": "application/json", **({"X-API-Key": APIKEY} if APIKEY else {})}
DATA_DIR = os.environ.get("PRISMCORTEX_DATA", ".prismcortex_data")
os.makedirs(DATA_DIR, exist_ok=True)

# Fixed, realistic workload — deterministic input (no randomness); the model calls
# behind the server are real.
# Realistic, verbose chat turns — the kind of thing an append-log keeps in full, but
# whose durable gist is small. This is what makes the memory-savings number honest.
FACTS = [
    "Hey team, quick intro since I'm new to the channel — I'm Amin and I'll be leading the platform team from now on, so route platform questions my way.",
    "Just locking in the number from this morning's planning meeting: our production deploy budget came in at $40,000 per quarter for the platform org.",
    "For everyone's reference, the primary database is Postgres 16 and it's hosted over in the us-east-1 region.",
    "We've gone ahead and standardized on the Gemini 2.5 Flash model as the default for all of our agents going forward.",
    "Friendly reminder that the on-call rotation is weekly and it kicks off on Mondays, so please arrange your swaps around that.",
    "If anyone needs to point a test client somewhere, our staging environment runs over in us-west-2.",
    "Compliance asked me to put on the record that the data retention policy is 90 days for raw logs, no exceptions.",
    "Quick CI/CD note for the team: we use GitHub Actions for CI and we deploy through Azure Container Instances.",
    "Reminder that the SRE team owns the incident response runbook, so please loop them in on anything that looks like a sev1.",
    "Worth keeping in mind before any risky deploy — our error budget is only 0.1 percent monthly downtime.",
    "Heads up, the API gateway rate limit is currently set to 100 requests per second per client.",
    "Security signed off and confirmed that all customer data is encrypted with AES-256 while it's at rest.",
    "ok thanks everyone, super helpful",          # salience gate should skip (no model call)
    "got it, really appreciate the rundown",       # skip
    "One more for the docs — the frontend is a Next.js app and it's deployed on Vercel.",
    "And we run nightly database backups every day at 02:00 UTC, fully automated.",
]
QUERIES = [
    "What is our deploy budget?",
    "Which database do we use and where is it hosted?",
    "What model do we default to for agents?",
    "Who leads the platform team?",
    "When does the on-call rotation start?",
    "What is our API gateway rate limit?",
]
CORRECTION = "Actually, correction on an earlier number — finance just updated it, our deploy budget is now $55,000 per quarter."
CORRECTION_QUERY = "What is our deploy budget?"

# The bulk of any real chat log: conversational filler + verbatim repeats, none of which
# is new knowledge. The append-log keeps every byte; the salience gate / idempotent memo
# discard all of it. (The last three are verbatim repeats of FACTS — idempotent skips.)
# Every line must be discarded with ZERO model calls: each is either <=2 words / a
# courtesy phrase (salience gate skips) or a verbatim repeat of an established fact
# (idempotent memo skip). That's what makes "the log keeps it, the graph doesn't" honest.
CHATTER = [
    "ok", "thanks", "thanks!", "sounds good", "got it", "will do", "ok cool",
    "yep", "agreed", "noted", "cool cool", "nice one", "makes sense", "ack",
    "brb", "back now", "haha nice", "no worries", "sounds great", "ok thanks",
    "yes please", "good call", "thank you", "all good",
    FACTS[2], FACTS[3], FACTS[4],  # verbatim repeats → idempotent skip, no model call
]


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


def _retry(fn, attempts: int = 4, retry_429: bool = False):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except urllib.error.HTTPError as exc:
            last = exc
            if retry_429 and exc.code == 429:
                time.sleep(0.5 * (i + 1))
                continue
            raise
        except (urllib.error.URLError, ConnectionError, OSError) as exc:  # transient
            last = exc
            time.sleep(0.4 * (i + 1))
    raise last


def _post(path: str, payload: dict, timeout: float = 60.0, *, retry_429: bool = False) -> dict:
    data = json.dumps(payload).encode()

    def call():
        req = urllib.request.Request(SERVER + path, data=data, headers=_HEADERS, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())

    return _retry(call, retry_429=retry_429)


def _get(path: str, timeout: float = 30.0) -> dict:
    def call():
        req = urllib.request.Request(SERVER + path, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())

    return _retry(call)


def _pct(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    return round(s[min(len(s) - 1, int(round((p / 100) * (len(s) - 1))))], 2)


def wait_for_health(timeout: float = 180.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if _get("/health").get("ok"):
                print(f"[driver] server healthy at {SERVER}")
                return
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(2)
    raise SystemExit(f"[driver] server at {SERVER} never became healthy")


def bench_ingest() -> dict:
    print("\n[1] INGEST")
    lat, committed, skipped, staged = [], 0, 0, 0
    for f in FACTS:
        r = _post("/digest", {"text": f, "source_id": f"fact:{hash(f) & 0xffffff}"})
        lat.append(r["ms"])
        oc = r["outcome"]
        committed += oc in ("committed", "reinforced")
        skipped += oc == "skipped"
        staged += oc == "staged"
        print(f"    {oc:10} band={r['band']:9} {r['ms']:7.1f}ms  {f[:46]!r}")
    return {
        "n": len(FACTS), "committed": committed, "skipped": skipped, "staged": staged,
        "latency_ms": {"p50": _pct(lat, 50), "p95": _pct(lat, 95), "p99": _pct(lat, 99), "max": round(max(lat), 2)},
    }


def bench_determinism(repeats: int = 5) -> dict:
    print(f"\n[2] DETERMINISM  ({repeats}x per query, across the network)")
    all_identical = True
    hits = misses = 0
    miss_lat, hit_lat = [], []
    for q in QUERIES:
        answers = []
        for _ in range(repeats):
            r = _post("/recall", {"query": q})
            answers.append(r["answer"])
            if r["cache_hit"]:
                hits += 1
                hit_lat.append(r["ms"])
            else:
                misses += 1
                miss_lat.append(r["ms"])
        identical = len(set(answers)) == 1
        all_identical &= identical
        print(f"    identical={identical}  -> {answers[0][:60]!r}")
    return {
        "queries": len(QUERIES), "repeats": repeats, "all_byte_identical": all_identical,
        "cache_hits": hits, "cache_misses": misses,
        "miss_latency_ms": {"p50": _pct(miss_lat, 50), "p95": _pct(miss_lat, 95)},
        "hit_latency_ms": {"p50": _pct(hit_lat, 50), "p95": _pct(hit_lat, 95)},
    }


def bench_reconsolidation() -> dict:
    print("\n[3] RECONSOLIDATION + TIME-TRAVEL")
    before = _post("/recall", {"query": CORRECTION_QUERY})["answer"]
    _post("/digest", {"text": CORRECTION})
    after = _post("/recall", {"query": CORRECTION_QUERY})["answer"]
    audit = _get("/audit")
    print(f"    before: {before[:60]!r}")
    print(f"    after:  {after[:60]!r}")
    print(f"    changed={before != after}  superseded_retained={audit['superseded_retained']}")
    return {"before": before, "after": after, "answer_changed": before != after,
            "superseded_retained": audit["superseded_retained"], "audit": audit}


def bench_consolidation() -> dict:
    print("\n[*] CONFLICT RESOLUTION  (a new value supersedes the old; history kept)")
    _post("/digest", {"text": "The cache TTL is 60 seconds."})
    base = _post("/recall", {"query": "What is the cache TTL?"})["answer"]
    r = _post("/digest", {"text": "The cache TTL is 300 seconds."})  # conflicting value
    _post("/sleep", {})  # consolidate, in case it was deferred to the staging buffer
    after = _post("/recall", {"query": "What is the cache TTL?"})["answer"]
    aud = _get("/audit")
    path = "staged->sleep" if r["outcome"] == "staged" else f"inline ({r['outcome']})"
    print(f"    {base[:28]!r} -> {after[:28]!r}   via {path}")
    return {
        "path": path,
        "conflict_outcome": r["outcome"],
        "answer_updated": "300" in after and "300" not in base,
        "history_retained": aud["superseded_retained"] > 0,
    }


def bench_throughput(total: int = 240, concurrency: int = 20) -> dict:
    print(f"\n[4] THROUGHPUT  ({total} concurrent cached recalls, c={concurrency})")
    q = QUERIES[0]
    _post("/recall", {"query": q})  # warm the cache

    def one(_):
        t0 = time.perf_counter()
        _post("/recall", {"query": q})
        return (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    lat = []
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        for fut in as_completed([ex.submit(one, i) for i in range(total)]):
            lat.append(fut.result())
    dur = time.perf_counter() - t0
    rps = round(total / dur, 1)
    print(f"    {total} reqs in {dur:.2f}s  ->  {rps} req/s   p50={_pct(lat,50)}ms p95={_pct(lat,95)}ms p99={_pct(lat,99)}ms")
    return {"requests": total, "concurrency": concurrency, "duration_s": round(dur, 2), "rps": rps,
            "latency_ms": {"p50": _pct(lat, 50), "p95": _pct(lat, 95), "p99": _pct(lat, 99)}}


def bench_memory(session_loops: int = 25) -> dict:
    print("\n[5] MEMORY SAVINGS  (the graph plateaus; the log grows with every turn)")
    before = _get("/memory_stats")
    turns = 0
    for _ in range(session_loops):  # simulate an ongoing working session
        for c in CHATTER:
            _post("/digest", {"text": c})
            turns += 1
    s = _get("/memory_stats")
    print(f"    + simulated {turns} more conversation turns (chit-chat + repeats, all discarded)")
    print(f"    graph edges before -> after those {turns} turns: "
          f"{before['graph_current_edges']} -> {s['graph_current_edges']}  (plateau)")
    print(f"    append-log would store : {s['raw_bytes_ingested']:>7} bytes")
    print(f"    PrismCortex gist graph : {s['gist_bytes']:>7} bytes  "
          f"({s['graph_nodes']} nodes / {s['graph_current_edges']} edges)")
    print(f"    -> {s['compression_ratio_gist']}x smaller — and the gap widens with every turn")
    s["session_turns"] = turns
    s["edges_before_session"] = before["graph_current_edges"]
    return s


def _parallel_bench(
    label: str,
    total: int,
    concurrency: int,
    work: Callable[[int], None],
    *,
    timeout: float = 60.0,
) -> dict:
    """Run `total` requests at `concurrency`; track latency + error types."""
    print(f"\n[*] {label}  ({total} req, c={concurrency}, timeout={timeout}s)")

    def one(i: int):
        t0 = time.perf_counter()
        err = None
        try:
            work(i)
        except Exception as exc:  # noqa: BLE001
            err = type(exc).__name__
        return (time.perf_counter() - t0) * 1000, err

    t0 = time.perf_counter()
    lat: list[float] = []
    err_counts: Counter[str] = Counter()
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        for fut in as_completed([ex.submit(one, i) for i in range(total)]):
            ms, err = fut.result()
            lat.append(ms)
            if err:
                err_counts[err] += 1
    dur = time.perf_counter() - t0
    errors = sum(err_counts.values())
    rps = round(total / dur, 1) if dur else 0.0
    err_detail = dict(sorted(err_counts.items()))
    print(f"    {total} reqs in {dur:.2f}s  ->  {rps} req/s   errors={errors}   "
          f"p50={_pct(lat,50)}ms p95={_pct(lat,95)}ms p99={_pct(lat,99)}ms")
    if err_detail:
        print(f"    error types: {err_detail}")
    return {
        "total": total,
        "concurrency": concurrency,
        "timeout_s": timeout,
        "duration_s": round(dur, 2),
        "rps": rps,
        "errors": errors,
        "error_rate": round(errors / total, 5) if total else 0.0,
        "error_types": err_detail,
        "latency_ms": {"p50": _pct(lat, 50), "p95": _pct(lat, 95), "p99": _pct(lat, 99)},
    }


def bench_recall_load(
    total: int | None = None,
    concurrency: int | None = None,
    *,
    label: str = "RECALL LOAD (cached reads only)",
) -> dict:
    """Sustained cached-read load — isolates recall path from digest backlog."""
    total = total if total is not None else _env_int("BENCH_RECALL_LOAD_TOTAL", 2000)
    concurrency = concurrency if concurrency is not None else _env_int("BENCH_RECALL_LOAD_C", 20)
    for q in QUERIES:
        _post("/recall", {"query": q})  # warm caches

    def work(i: int) -> None:
        _post("/recall", {"query": QUERIES[i % len(QUERIES)]}, timeout=30.0, retry_429=True)

    return _parallel_bench(
        label,
        total,
        concurrency,
        work,
        timeout=30.0,
    )


def _stress_recall_enabled() -> bool:
    return os.environ.get("BENCH_STRESS_RECALL", "").lower() in ("1", "true", "yes")


def bench_stress_recall_load() -> dict:
    """Optional ceiling probe — not part of reference SLO (default c=50)."""
    total = _env_int("BENCH_STRESS_RECALL_TOTAL", 2000)
    concurrency = _env_int("BENCH_STRESS_RECALL_C", 50)
    result = bench_recall_load(
        total=total,
        concurrency=concurrency,
        label="STRESS RECALL (optional ceiling probe)",
    )
    result["role"] = "optional_stress_probe"
    result["included_in_slo_pass"] = False
    return result


def bench_digest_load(
    total: int | None = None,
    concurrency: int | None = None,
) -> dict:
    """Sustained write load — salience-gated chatter; c capped near digest semaphore."""
    total = total if total is not None else _env_int("BENCH_DIGEST_LOAD_TOTAL", 400)
    concurrency = concurrency if concurrency is not None else _env_int("BENCH_DIGEST_LOAD_C", 16)
    chatter = ["ok thanks", "got it", "thanks", "sounds good", "noted"]

    def work(i: int) -> None:
        _post("/digest", {"text": chatter[i % len(chatter)]}, timeout=90.0, retry_429=True)

    return _parallel_bench(
        "DIGEST LOAD (salience-skipped chatter)",
        total,
        concurrency,
        work,
        timeout=90.0,
    )


def bench_mixed_load(
    total: int | None = None,
    concurrency: int | None = None,
) -> dict:
    """Optional mixed R/W smoke — lower concurrency than recall-only burst."""
    total = total if total is not None else _env_int("BENCH_MIXED_LOAD_TOTAL", 500)
    concurrency = concurrency if concurrency is not None else _env_int("BENCH_MIXED_LOAD_C", 20)
    for q in QUERIES:
        _post("/recall", {"query": q})

    def work(i: int) -> None:
        if i % 5 == 0:
            _post("/digest", {"text": "ok thanks"}, timeout=90.0, retry_429=True)
        else:
            _post("/recall", {"query": QUERIES[i % len(QUERIES)]}, timeout=30.0, retry_429=True)

    return _parallel_bench(
        "MIXED LOAD (20% writes, smoke test)",
        total,
        concurrency,
        work,
        timeout=90.0,
    )


def bench_load() -> dict:
    """Split sustained load: reference recall @ c=20, digest, mixed; optional stress @ c=50."""
    recall = bench_recall_load()
    recall["role"] = "reference"
    digest = bench_digest_load()
    mixed = bench_mixed_load()
    stress_recall = bench_stress_recall_load() if _stress_recall_enabled() else None

    reference_errors = recall["errors"] + digest["errors"] + mixed["errors"]
    reference_total = recall["total"] + digest["total"] + mixed["total"]
    stress_errors = stress_recall["errors"] if stress_recall else 0

    out: dict = {
        "recall": recall,
        "digest": digest,
        "mixed": mixed,
        "reference_errors": reference_errors,
        "reference_total": reference_total,
        "reference_error_rate": round(reference_errors / reference_total, 5) if reference_total else 0.0,
        "reference_slo_pass": reference_errors == 0,
        "slo_pass": reference_errors == 0,
        "errors": reference_errors + stress_errors,
        "total": reference_total + (stress_recall["total"] if stress_recall else 0),
        "error_rate": round((reference_errors + stress_errors) / (reference_total + (stress_recall["total"] if stress_recall else 0)), 5)
        if reference_total + (stress_recall["total"] if stress_recall else 0)
        else 0.0,
    }
    if stress_recall is not None:
        out["stress_recall"] = stress_recall
        out["stress_slo_pass"] = stress_errors == 0
    return out


def main() -> None:
    print(f"=== PrismCortex benchmark driver -> {SERVER} ===")
    wait_for_health()
    _post("/reset", {})

    results = {
        "server_url": SERVER,
        "timestamp": round(time.time(), 1),
        "ingest": bench_ingest(),
        "determinism": bench_determinism(),
        "reconsolidation": bench_reconsolidation(),
        "consolidation": bench_consolidation(),
        "throughput": bench_throughput(),
        "load": bench_load(),
        "memory": bench_memory(),
    }
    results["server_metrics"] = _get("/metrics")
    results["cost"] = {
        "gemini_calls": results["server_metrics"]["gemini_calls"],
        "cache_hit_rate": results["server_metrics"]["cache_hit_rate"],
        "recalls_total": results["server_metrics"]["counts"]["recall"],
    }

    out = os.path.join(DATA_DIR, "results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 64 + "\nSCORECARD\n" + "=" * 64)
    d, r, t, c, m, con = (results["determinism"], results["reconsolidation"], results["throughput"],
                          results["cost"], results["memory"], results["consolidation"])
    print(f"  cross-container determinism : {'PASS' if d['all_byte_identical'] else 'FAIL'}  "
          f"({d['cache_hits']} hits / {d['cache_misses']} misses)")
    print(f"  reconsolidation + time-travel: {'PASS' if r['answer_changed'] and r['superseded_retained'] else 'FAIL'}  "
          f"({r['superseded_retained']} superseded facts retained)")
    print(f"  conflict resolution          : {'PASS' if con['answer_updated'] and con['history_retained'] else 'FAIL'}  "
          f"(via {con['path']})")
    print(f"  memory savings (gist vs log) : {m['compression_ratio_gist']}x smaller  "
          f"({m['raw_bytes_ingested']}B -> {m['gist_bytes']}B gist)")
    print(f"  throughput (cached recalls)  : {t['rps']} req/s  p95={t['latency_ms']['p95']}ms")
    ld = results["load"]
    lr, ldig, lmix = ld["recall"], ld["digest"], ld["mixed"]
    print(f"  recall load (c={lr['concurrency']})     : {lr['rps']} req/s  "
          f"errors={lr['errors']}/{lr['total']}  p99={lr['latency_ms']['p99']}ms")
    print(f"  digest load (c={ldig['concurrency']})   : {ldig['rps']} req/s  "
          f"errors={ldig['errors']}/{ldig['total']}  p99={ldig['latency_ms']['p99']}ms")
    print(f"  mixed smoke (c={lmix['concurrency']})     : {lmix['rps']} req/s  "
          f"errors={lmix['errors']}/{lmix['total']}  p99={lmix['latency_ms']['p99']}ms")
    if ld.get("stress_recall"):
        ls = ld["stress_recall"]
        print(f"  stress recall (c={ls['concurrency']})   : {ls['rps']} req/s  "
              f"errors={ls['errors']}/{ls['total']}  (optional probe, not reference SLO)")
    print(f"  load SLO (reference phases)  : {'PASS' if ld['slo_pass'] else 'FAIL'}  "
          f"({ld['reference_errors']}/{ld['reference_total']} errors — recall+digest+mixed @ c≤20)")
    if ld.get("stress_recall"):
        ls = ld["stress_recall"]
        print(f"  stress SLO (optional c={ls['concurrency']}): "
              f"{'PASS' if ld.get('stress_slo_pass') else 'FAIL'}  "
              f"({ls['errors']}/{ls['total']} errors — ceiling probe only)")
    print(f"  cost: {c['gemini_calls']} Gemini calls for {c['recalls_total']} recalls  "
          f"(cache hit rate {c['cache_hit_rate']})")
    print(f"\n  full results -> {out}")

    # Emit the full results to stdout so they're captured from container logs
    # (no shared file system required).
    print("\nRESULTS_JSON_BEGIN")
    print(json.dumps(results))
    print("RESULTS_JSON_END")


if __name__ == "__main__":
    main()
