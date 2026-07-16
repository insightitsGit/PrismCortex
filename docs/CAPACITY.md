# PrismCortex capacity guide (reference hardware)

Honest starting points from Azure E2E + scale benches. Re-run after your deployment shape.

**Load benchmark story (what we fixed):** [LOAD_BENCHMARK.md](LOAD_BENCHMARK.md)

## Single container (4 vCPU / 8 GB default for Azure bench, `prism` backend)

| Workload | Observed (v0.2.1) | Notes |
|---|---|---|
| Cached recall p50 | ~5–21 ms | Includes MiniLM query projection |
| First render (cache miss) p50 | ~700 ms | One Gemini call |
| Digest (fact extraction) p50 | ~3.1 s | Salience gate skips chatter |
| Throughput (cached, c=20) | **141 req/s** | Up from 74 on 2 vCPU |
| **Reference load SLO** | **PASS** — recall c=20 + mixed c=20 + digest c=16, 0 errors | `slo_pass` |
| Optional stress recall (c=50, 2000 req) | 6.2% client timeouts | `BENCH_STRESS_RECALL=1` only — not reference sizing |
| Mixed smoke (c=20, 500 req) | **0 errors** | 20% writes |
| Digest load (c=16, 400 req) | **0 errors** | Matches digest semaphore |
| Graph size (linear scan) | Fine to ~10k facts | hit@8 ≈ 0.98 @ 128-dim |
| Graph size (IVF ANN) | Enable `PRISMCORTEX_USE_ANN=1` | Activates at 5k nodes default |

Legacy reference: **2 vCPU / 4 GB** monolithic mixed load at c=50 saw 2.5% client timeouts (recalls
queued behind digests on the default Starlette thread pool). **Fixed in v0.2.1** — see [LOAD_BENCHMARK.md](LOAD_BENCHMARK.md).

## Tuning

- `PRISMCORTEX_READ_POOL=64` — dedicated thread pool for `/recall` (not starved by digest)
- `PRISMCORTEX_MAX_CONCURRENT_DIGEST=16` — write pool size + digest backpressure (429 when saturated)
- `UVICORN_LIMIT_CONCURRENCY=256` — max in-flight HTTP connections (entrypoint)
- `PRISMCORTEX_RATE_LIMIT_RPM=600` — per-key requests/minute (0 = off)
- `PRISMCORTEX_ANN_THRESHOLD=5000` — switch to IVF retrieval
- `PRISMCORTEX_STAGING_WARN=50` — health alert when labile backlog grows
- `SRV_CPU` / `SRV_MEM` — Azure deploy sizing in `deploy/run_only.sh` (default **4 / 8**)

### Benchmark load env (driver)

Split load avoids queueing cached recalls behind digest work (root cause of v0.2 mixed-load timeouts):

| Variable | Default | Purpose |
|---|---|---|
| `BENCH_RECALL_LOAD_TOTAL` | 2000 | Cached `/recall` burst size |
| `BENCH_RECALL_LOAD_C` | 20 | Reference recall concurrency |
| `BENCH_STRESS_RECALL` | 0 | Set `1` to run optional c=50 ceiling probe |
| `BENCH_STRESS_RECALL_C` | 50 | Stress recall concurrency |
| `BENCH_DIGEST_LOAD_TOTAL` | 400 | Salience-skipped `/digest` burst (≈20% of old mixed total) |
| `BENCH_DIGEST_LOAD_C` | 16 | Digest concurrency (≤ `MAX_CONCURRENT_DIGEST`) |
| `BENCH_MIXED_LOAD_TOTAL` | 500 | Optional combined smoke test |
| `BENCH_MIXED_LOAD_C` | 20 | Mixed concurrency (keep low) |

## Horizontal scaling

See [SCALING.md](SCALING.md). PrismLib cache is per-tenant durable; graph is in-process today — scale reads via multiple read-only replicas with shared cache invalidation (Chorus) in commercial tier.
