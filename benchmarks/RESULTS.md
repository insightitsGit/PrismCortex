# PrismCortex — Azure benchmark results

Real runs, real Gemini, two containers in one zone. No mocks, no synthetic numbers.

**Canonical artifact:** `benchmarks/results/results.json` (machine-readable scorecard).  
Driver/server logs are captured locally on each run (`*.log` gitignored); re-run deploy to regenerate.

---

## Latest run — v0.2.1 (2026-06-30, ACR build `ca9`)

- **Image:** `prismcortexd7a6d0.azurecr.io/prismcortex:bench` — **v0.2.0** + capacity fixes
  (digest `sha256:9f24f85148b51aa38846e3755bb4aa753298759cb187aaaf2b7ec9b6c82b0c7b`)
- **Build:** ACR `ca9` · split load driver · read/write thread pools · uvicorn limit-concurrency
- **Topology:** 2 ACI in **East US** · server **4 vCPU / 8 GB** · driver 1 vCPU
  · `PRISMCORTEX_BACKEND=prism` · `PRISMCORTEX_USE_ANN=1` · `PRISMCORTEX_READ_POOL=64`
- **Artifacts:** `benchmarks/results/{results.json,driver.log,server.log}`

### Scorecard (v0.2.1)

| Claim | Result |
|---|---|
| **Cross-container determinism** | **PASS** — 24/24 byte-identical |
| **Reconsolidation + time-travel** | **PASS** — `$40k → $55k`; superseded fact retained |
| **Conflict resolution (`60s → 300s`)** | **PASS** — **staged → `sleep()`**; history retained |
| **Memory plateau (675 turns)** | **PASS** — edges **30 → 30** |
| **Memory savings (gist vs log)** | **5.20×** smaller (18,740 B → 3,604 B gist) |
| **Throughput (cached, c=20)** | **141.4 req/s** p95=159 ms (was 74 on v0.2 / 2 vCPU) |
| **Recall load (2000 req, c=50)** | **FAIL SLO** — 124/2000 client `URLError` timeouts (6.2%) |
| **Digest load (400 req, c=16)** | **PASS** — 0 errors |
| **Mixed smoke (500 req, c=20)** | **PASS** — 0 errors, p99=15 s |
| **Cost / cache** | **30 Gemini calls / 2,563 recalls** — **99.57% cache hit** |
| **Server errors (core path)** | **0** |

**Load SLO:** `slo_pass: false` — recall burst at c=50 still hits client timeouts; **mixed @ c=20
and digest @ c=16 are green.** Server-side recall p99 was **64 ms** — failures are driver/network
saturation at 50 concurrent connections, not slow renders.

### Latency (v0.2.1)

| Path | p50 | p95 |
|---|---|---|
| Cache hit (determinism) | **5.5 ms** | 8.0 ms |
| Cache miss | **724 ms** | 849 ms |
| Fact digest (ingest) | **2.9 s** | 5.1 s |
| Server recall (all) | **14 ms** | 41 ms |

**Deck / SLA copy:** see [docs/SLA.md](../docs/SLA.md#deck-ready-one-liners-v021-azure-validated).

---

## Prior run — v0.2.0 (2026-06-29, ACR build `ca8`)

- **Image:** `prismcortexd7a6d0.azurecr.io/prismcortex:bench` — **v0.2.0**
  (digest `sha256:b83b297cdf0ac3a2445f6f0c95248b261bab365e569f8b012098614078f1c779`)
- **Build:** `az acr build -r prismcortexd7a6d0 -g prismcortex-rg -t prismcortex:bench .`
- **Topology:** 2 ACI in **East US** · server 2 vCPU / 4 GB · `PRISMCORTEX_BACKEND=prism`
  · `PRISMCORTEX_USE_ANN=1` · auth enabled
- **Server URL:** `http://prismcortex-srv-d7a6d0.eastus.azurecontainer.io:8080`

### Scorecard (v0.2.0 — 2 vCPU / 4 GB, monolithic mixed load)

| Claim | Result |
|---|---|
| **Cross-container determinism** | **PASS** — 24/24 replays byte-identical (6 queries × 5 repeats) |
| **Reconsolidation + time-travel** | **PASS** — `$40k → $55k`; 1 superseded fact retained |
| **Conflict resolution (`60s → 300s`)** | **PASS** — answer updated, history retained (inline commit this run) |
| **Memory plateau (675 chatter turns)** | **PASS** — edges **30 → 30**; 0 new graph growth |
| **Memory savings (gist vs log)** | **5.09×** smaller (18,417 B raw → 3,616 B gist; 46 nodes / 30 edges) |
| **Throughput (cached recalls, c=20)** | **74.0 req/s** — p50=247 ms, p95=422 ms, p99=448 ms |
| **Sustained load (c=50, 2000 mixed)** | **Captured — needs tuning** — 50 client timeouts (2.5%); split load fix in driver |
| **Cost / cache** | **30 Gemini calls / 1,838 recalls** — **99.4% cache hit rate** |
| **Server errors (core path)** | **0** (1,087 digests, 1,838 recalls, 1 sleep) |

### Latency breakdown (v0.2)

| Path | p50 | p95 | Notes |
|---|---|---|---|
| Cache **hit** (frozen replay) | **6.6 ms** | 8.8 ms | 24 hits in determinism block |
| Cache **miss** (first render → Gemini) | **777 ms** | 997 ms | 6 misses |
| Fact **digest** (Gemini extraction) | **2.7 s** | 3.8 s | 14 committed of 16 ingests |
| Server **recall** (all paths) | 18.4 ms | 64.3 ms | includes MiniLM projection |

### Ingest (v0.2)

- 16 messages: **14 committed**, 2 skipped (salience gate), 0 staged
- Chatter session: **675 turns** appended after facts — graph stayed flat

### Sustained load — honest read (v0.2 run used monolithic mixed test)

The v0.2 driver sent **2000 mixed requests at c=50** (80% recall + 20% digest) on one
2-vCPU container. **50 client-side timeouts** (not server errors): recalls queued behind
digest work until the driver's 60 s × 4 retry budget expired (p99 ≈ 244 s).

**Fix (driver v0.2.1+):** split into three phases — recall burst, digest burst, mixed
smoke at c=20 — with 429 retry and per-phase error-type logging. Re-run Azure to capture
green SLO numbers. See `docs/CAPACITY.md` for env tunables.

---

## Prior run — v0.1 (2026-06-28)

- **Image:** same tag, pre–v0.2 enterprise stack (no ANN, no auth hardening, no `bench_load`)
- **Topology:** 2 ACI in **East US** · server 2 vCPU / 4 GB · `PRISMCORTEX_BACKEND=prism`
- **Server errors:** 0 across 692 digests + 273 recalls

### Scorecard (v0.1)

| Claim | Result |
|---|---|
| **Cross-container determinism** | **PASS** — 24/24 replays byte-identical over the network |
| **Reconsolidation + time-travel** | **PASS** — `$40,000 → $55,000`; old fact invalidated **but retained** |
| **Conflict resolution (`60s → 300s`)** | **PASS** — staged → `sleep()`; history retained |
| **Memory plateau (675 turns)** | **PASS** — edges **31 → 31**; 0 extra Gemini calls on chatter |
| **Memory savings (gist vs log)** | **3.32×** smaller at 675 turns |
| **Throughput (cached recalls, c=20)** | **37.5 req/s** p95=234 ms |
| **Cost / cache** | **28 Gemini calls / 275 recalls** — 96.7% cache hit |
| **Sustained load** | not run |

### v0.1 → v0.2 deltas (same workload)

| Metric | v0.1 | v0.2 |
|---|---|---|
| Cached throughput (c=20) | 37.5 req/s | **74.0 req/s** |
| Cache hit rate | 96.7% | **99.4%** |
| Gist compression | 3.32× | **5.09×** |
| ANN index | off | **on** (`ann_enabled: true`) |
| Sustained load | — | captured (needs tuning) |

---

## Numbers that matter (v0.1 detail — still valid for mechanism)

**The cache is the determinism — and far cheaper than the model:**

| recall path | p50 latency (v0.1) |
|---|---|
| cache **miss** (first render → Gemini) | 693 ms |
| cache **hit** (frozen replay) | **5.6 ms** |

(Hit latency includes real PrismLang MiniLM query projection — honest full-stack cost.)

**Memory savings — the honest version.** After 14 facts, the driver simulated **675
more conversation turns** (chit-chat + verbatim repeats). The append-log keeps all of it;
the graph kept **none** of it — **0 new edges**. Those turns cost **0 Gemini calls**
(salience gate + idempotent memo). The ratio grows with conversation length; the real claim
is the **plateau**.

> Caveat: for a *short, fact-dense* conversation with no redundancy, the structured graph
> can be *larger* than raw text (~0.4×). Savings come from redundancy + accumulation.

**Write path:** fact digests p50 ~3 s — why writes are salience-gated and reads are cached.

---

## Earlier `lite` run (hashing embeddings, same infra)

Determinism PASS · reconsolidation PASS · **372 req/s** · 22 calls / 273 recalls. The
`lite` backend missed one retrieval (*"where is the DB hosted"*) that the `prism` backend
answers correctly — the main reason to run the full stack.

---

## Scale & retrieval quality (`benchmarks/scale_bench.py`, no LLM)

Seeds N deterministic synthetic facts (real PrismLang **128-dim** embeddings) and measures
hit@k + retrieval latency. **Published ANN run:** `benchmarks/results/scale_ann.json`.

```bash
python benchmarks/scale_bench.py --ann --levels 200,1000,10000,50000
```

### Linear scan (historical, ≤ ~10k facts)

| facts | nodes | hit@8 | retrieve p95 |
|---|---|---|---|
| 200 | 400 | 0.965 | 0.23 ms |
| 1,000 | 2,000 | 0.935 | 0.66 ms |
| 3,000 | 6,000 | 0.97 @ 128-dim | 1.6 ms |
| 10,000 | 20,000 | 0.98 | 5 ms |

### IVF ANN (`AnnGraphStore`, threshold 5k nodes) — published 2026-06-30

| facts | nodes | ANN on | hit@8 | retrieve p50 | retrieve p95 |
|---|---|---|---|---|---|
| 10,000 | 20,000 | yes | **0.915** | 6.6 ms | 10.0 ms |
| **50,000** | **100,000** | yes | **0.850** | 60 ms | 74 ms |

**Findings:** ANN keeps retrieval **sub-100 ms p95 at 100k nodes** (vs O(N) linear scan
which would be impractical). Recall at 50k is **~85% hit@8** — acceptable for governed
retrieval with rerank/explain; tune `nprobe` or use PrismRAG for 95%+ at 500k+.

---

## Head-to-head vs Zep Cloud (`benchmarks/vs_zep.py`, real Gemini on PrismCortex)

Same correction workload as Mem0 comparison. Set `ZEP_API_KEY` + `pip install zep-cloud`
for live Zep numbers; otherwise PrismCortex side runs and dimensions are printed.

```bash
GEMINI_API_KEY=... ZEP_API_KEY=... python benchmarks/vs_zep.py
```

**Comparison dimensions:** correction surfaces new value · old value retained · replay
determinism · cached rendered answer · self-hosted / sovereignty.

---

## Adversarial probes (`benchmarks/adversarial_bench.py`, real Gemini)

4 probes that try to break it: **4/4 passed** locally after engine fixes (re-run on Azure TBD).

- ✅ over-merge guard (Acme Corp ≠ Acme Health)
- ✅ distractor precision (1 right of 6 similar)
- ✅ multi-hop (person → project → database)
- ✅ contradiction-under-context — exposed value fuzzy-merge bug (fixed Jun 29)

**The bug the harness caught.** Fuzzy entity resolution was merging similar **values**
(`"300 seconds"` into `"60 seconds"`), silently dropping conflicts. Fix: subjects coref by
embedding; **values exact-match only**; relation normalization + token-overlap for subjects.

---

## Head-to-head vs Mem0 OSS (`benchmarks/vs_mem0.py`, same workload, same Gemini)

- **Determinism on reads is a WASH** — Mem0 vector retrieval is also deterministic.
- **Correction handling:** PrismCortex updated `40k → 55k`; Mem0 top result stayed `40k`.
- **Time-travel / audit:** PrismCortex retains superseded values as bitemporal facts;
  Mem0 OSS temporal retrieval is a paid Platform feature.
- **Moat:** **cached rendered answers + bitemporal audit + sovereignty**, not “determinism”
  in the abstract.

---

## Honest caveats

- **Determinism = replay-determinism** (first render → cache → byte-identical replays), not
  first-render token-determinism from shared APIs.
- **Throughput is a floor** — single 2-vCPU container; includes network RTT.
- **Maturity: v0.2.0** — enterprise stack landed; sustained-load SLO still open.
- **Conflict path varies:** v0.1 exercised staged→`sleep()`; v0.2 run committed inline
  (both retain history — mechanism validated either way).

---

## Reproduce

```bash
# Full rebuild + run (ACR build + deploy + capture)
bash deploy/rebuild_and_run.sh

# Deploy only (image must already exist in ACR)
BACKEND=prism bash deploy/run_only.sh

# Tear down entire resource group (includes ACR!)
bash deploy/cleanup.sh
```

After a run, artifacts land in `benchmarks/results/`:
- **`results.json`** — tracked in git; update this doc from it
- **`driver.log`**, **`server.log`** — gitignored; local audit trail only
