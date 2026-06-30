# Load benchmark — what broke, what we fixed, how to read the numbers

> **Canonical artifacts:** [benchmarks/results/results.json](../benchmarks/results/results.json) ·
> [benchmarks/RESULTS.md](../benchmarks/RESULTS.md) · driver: [benchmarks/driver.py](../benchmarks/driver.py)

This doc explains the Azure sustained-load story so buyers, agents, and engineers do not
misread **`slo_pass: false`** as “the server is broken.”

---

## TL;DR

| Question | Answer |
|----------|--------|
| Did we fix load? | **Yes — for production-shaped workloads.** Mixed @ c=20 and digest @ c=16 are **0 errors** after v0.2.1. |
| Why does `slo_pass` still say false? | The scorecard also runs an **aggressive recall-only stress test** at **c=50** (6.2% client timeouts). That is a **ceiling probe**, not our reference sizing. |
| What should sales cite? | **~20 concurrent clients / 4 vCPU**, mixed R/W, **141 req/s** cached, **0 server errors**. See [SLA.md](SLA.md). |
| Was it a server bug? | **No.** Server recall p99 was **64 ms** with **0 server errors**. Failures were **client-side timeouts** on the benchmark driver. |

---

## Timeline

### v0.2.0 (2026-06-29, ACR `ca8`) — problem identified

**Test design (flawed for read SLO):** one phase, **2000 mixed requests at c=50** — 80% `/recall`, 20% `/digest`.

**Hardware:** 1× Azure container, **2 vCPU / 4 GB**, single shared Starlette thread pool.

**Result:** **50 / 2000 client timeouts (2.5%)**, p99 ≈ 244 s. **0 server errors.**

**Root cause:** recalls **queued behind digest work** on one thread pool. The server kept
processing; the driver gave up after ~60 s × retries. This measured **contention**, not
slow memory logic.

### v0.2.1 (2026-06-30, ACR `ca9`) — fixes shipped + re-run

Three layers of fix, then a **split load driver** so each phase measures one thing.

| Fix | Where | What it does |
|-----|-------|--------------|
| **Split load phases** | `benchmarks/driver.py` | Recall burst, digest burst, mixed smoke — separate |
| **Read/write thread pools** | `server.py`, `server_helpers.py` | `/recall` on `pc-read` (64 threads); `/digest` on `pc-write` (16) |
| **Digest backpressure** | `server.py` | 429 when write pool saturated |
| **Uvicorn tuning** | `docker/entrypoint.sh` | `--limit-concurrency 256`, keep-alive 30 s |
| **Bigger Azure box** | `deploy/run_only.sh` | **4 vCPU / 8 GB** (was 2 / 4) |
| **Health wait** | `deploy/run_only.sh` | Driver waits for `/health` before load |
| **429 retry + error types** | `driver.py` | Retries rate-limits; logs `URLError` vs HTTP errors |

---

## v0.2.1 load results (after fixes)

| Phase | Requests | Concurrency | Errors | Verdict | Role |
|-------|----------|-------------|--------|---------|------|
| **Mixed smoke** | 500 | **c=20** | **0** | **PASS** | **Reference SLO** — realistic combined R/W |
| **Digest load** | 400 | c=16 | **0** | **PASS** | Write path + backpressure |
| **Recall burst** | 2000 | **c=50** | **124** (6.2%) | **FAIL** | **Stress test** — not reference sizing |
| **Throughput** | 240 | c=20 | 0 | **PASS** | 141 req/s cached (was 74 on 2 vCPU) |

**Server metrics during full run:** recall p99 **63.6 ms**, **0 server errors**, **0 rate-limited** (on core path).

### Two SLO fields in `results.json`

| Field | Meaning | v0.2.1 |
|-------|---------|--------|
| `reference_slo_pass` | Mixed + digest phases only (production-shaped) | **`true`** |
| `slo_pass` | All phases including recall stress @ c=50 | **`false`** |

Use **`reference_slo_pass`** for decks and sizing. Use recall @ c=50 as “headroom / scale-out needed,” not GA blocker for ~20-client deployments.

---

## Why recall @ c=50 still times out

This phase fires **50 simultaneous HTTP clients** at one **4 vCPU** container for **~522 seconds**
(2000 cached recalls, 3.8 req/s effective — queueing at the driver connection layer).

Evidence it is **not** slow renders:

- Server-side recall p95 **41 ms**, p99 **64 ms**
- **0** unhandled 5xx, **0** server-reported errors
- Error type: **`URLError`** (client timeout at 30 s), not HTTP 5xx

Likely contributors: driver thread pool + TCP connection count + single-node Azure ACI limits.
**Fix for c=50 green:** horizontal read replicas ([SCALING.md](SCALING.md)), lower
`BENCH_RECALL_LOAD_C`, or longer driver timeout — not a memory correctness issue.

---

## Architecture before vs after

### Before (v0.2.0)

```
2000 mixed @ c=50 ──▶ one thread pool ──▶ digest threads block recall ──▶ client timeouts
                      (2 vCPU)
```

### After (v0.2.1)

```
Phase 1: 2000 recall @ c=50  ──▶ pc-read pool (64)     ──▶ stress (some client timeouts)
Phase 2: 400 digest @ c=16   ──▶ pc-write pool (16)    ──▶ PASS
Phase 3: 500 mixed @ c=20    ──▶ read + write pools    ──▶ PASS (reference SLO)
                                 (4 vCPU / 8 GB)
```

---

## Reproduce

```bash
# Full Azure E2E (build)**builds image, deploys, runs driver, writes results.json**
BACKEND=prism bash deploy/run_only.sh

# Tune load phases locally (server must be running)
export BENCH_RECALL_LOAD_C=20      # lower stress concurrency
export BENCH_MIXED_LOAD_C=20       # reference mixed (default)
python benchmarks/driver.py        # or run via Azure driver container
```

Env reference: [CAPACITY.md](CAPACITY.md#benchmark-load-env-driver).

---

## What to say externally

**Do say:**

- “Validated **mixed read/write at 20 concurrent clients with zero errors** on a single 4 vCPU node.”
- “**141 cached recalls/sec**; server-side recall p99 under **65 ms**.”
- “Load test methodology documented; recall-only burst at 50 clients is a stress probe.”

**Do not say:**

- “50 concurrent clients per node with zero failures.”
- “Load SLO fully green” without qualifying the c=50 stress phase.

---

## Related docs

- [CAPACITY.md](CAPACITY.md) — sizing and env tunables
- [SLA.md](SLA.md) — deck one-liners and reference SLO table
- [SCALING.md](SCALING.md) — scale-out beyond one node

*Last updated: 2026-06-30 · run: v0.2.1 ACR `ca9`*
