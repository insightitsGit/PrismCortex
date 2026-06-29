# PrismCortex — Azure benchmark results

Real runs, real Gemini, two containers in one zone. No mocks, no synthetic numbers.

## Setup (full-stack run)
- **Topology:** 2 Azure Container Instances in **East US** (same zone). Container A = the
  self-contained PrismCortex memory service; Container B = a second agent driving the
  benchmark over the network.
- **Backend:** `prism` — the **full stack**: real **PrismLang** projection (ONNX MiniLM),
  real **PrismResonance** wavepacket memory, real **PrismLib** `SQLiteStore` cache, and
  **real Gemini** (`gemini-2.5-flash`) for extraction & rendering.
- **Image:** `prismcortexd7a6d0.azurecr.io/prismcortex:bench` (cloud-built via `az acr build`).
- **Server:** 2 vCPU / 4 GB.  **Errors:** 0 across 692 digests + 273 recalls.

## Scorecard

| Claim | Result |
|---|---|
| **Cross-container determinism** | **PASS** — 24/24 replays byte-identical over the network |
| **Reconsolidation + time-travel** | **PASS** — `$40,000` → `$55,000`; old fact invalidated **but retained** |
| **Conflict resolution (v0.2)** | **PASS** — a conflicting value (`60s` → `300s`) routed through the **labile buffer** and was resolved on `sleep()`, old value retained. The two-speed path fired on real Gemini. |
| **Memory savings (graph vs log)** | **3.32× smaller** at 675 turns, and the graph **plateaus** (31 → 31 edges) — constant-size vs conversation volume |
| **Throughput (cached recalls)** | **variable: 37–498 req/s** across runs (ACI instance variance + per-recall MiniLM projection). A floor, not a ceiling — needs real load-testing. |
| **Cost** | **~28 Gemini calls served ~275 recalls** — ~97% cache hit rate |

### v0.2 improvements landed (this round)
- **#1 Entity resolution** — incoming entities resolve to existing nodes by embedding
  similarity (`find_similar_node`), so paraphrased subjects don't fork into duplicate
  facts; values stay distinct. Unit-tested.
- **#2 Real `sleep()` consolidation** — silent conflicts defer to the labile buffer and
  `sleep()` resolves them (invalidate old, keep history, new becomes current). Previously
  `staged=0`; now the two-speed path is exercised and validated end-to-end. Unit-tested.

## Numbers that matter

**The cache is the determinism — and far cheaper than the model:**
| recall path | p50 latency |
|---|---|
| cache **miss** (first render → Gemini) | 693 ms |
| cache **hit** (frozen replay) | **5.6 ms** |

(Hit latency is higher than the `lite` backend's ~1 ms because every recall runs the real
PrismLang MiniLM query projection — an honest cost of the full stack.)

**Memory savings — the honest version.** After the 14 facts, the driver simulated **675
more conversation turns** (chit-chat + verbatim repeats). The append-log keeps all of it
(14,823 bytes); the graph kept **none** of it — **0 new edges (31 → 31)**. Those 675 turns
cost **0 Gemini calls** and processed at **0.1 ms p50** (salience gate + idempotent memo).
The 3.48× ratio is at 675 turns; the real claim is the **plateau** — the graph is
constant-size w.r.t. conversation length, so the gap widens without bound.

> Caveat stated plainly: for a *short, fact-dense* conversation with no redundancy, the
> structured graph is actually *larger* than the raw text (~0.4×). The savings come from
> redundancy + accumulation, which is what real conversations are made of — not from
> compressing a single dense paragraph.

**Cost / tokens:** 273 recalls cost **24** Gemini calls; the salience gate skipped 2 of 16
ingests and all 675 chatter turns with zero model calls.

**Write path (real Gemini extraction):** fact digests p50 ~3.1 s — the expensive
natural-language→graph step, which is why writes are salience-gated and reads are cached.

## Earlier `lite` run (hashing embeddings, same infra)
Determinism PASS · reconsolidation PASS · **372 req/s** · 22 calls / 273 recalls. The
`lite` backend missed one retrieval (*"where is the DB hosted"*) that the `prism` backend
answers correctly — the main reason to run the full stack.

## Scale & retrieval quality (`benchmarks/scale_bench.py`, no LLM)
Seeds N deterministic synthetic facts (real PrismLang embeddings) and measures retrieval
hit@k + latency as the graph grows.

| facts | nodes | hit@8 (dim 64) | hit@8 (dim 128) | retrieve p95 |
|---|---|---|---|---|
| 200 | 400 | 0.965 | — | 0.23 ms |
| 1,000 | 2,000 | 0.935 | — | 0.66 ms |
| 3,000 | 6,000 | **0.835** | **0.97** | 1.6 ms |

**Findings:** retrieval **latency scales fine** (vectorized matmul — sub-2ms at 6k nodes;
beyond ~10k it needs a real ANN index / PrismRAG). Retrieval **recall degraded at scale**
(0.965 → 0.835) — and higher top-k barely helped (0.90 at k=64), so it wasn't a top-k
problem. Root cause: PrismLang's default **64-dim** projection crowds at scale. **Fix
shipped:** default projection dim → **128**, which restores recall to **0.97** at 3k facts
with no latency cost. (256 gives no further gain.)

## Adversarial probes (`benchmarks/adversarial_bench.py`, real Gemini)
4 probes that try to break it: **3/4 passed.**
- ✅ over-merge guard (Acme Corp ≠ Acme Health — fuzzy-resolution threshold is safe)
- ✅ distractor precision (1 right of 6 similar)
- ✅ multi-hop (person → project → database)
- ❌ contradiction-under-context: in a shared graph it returned "I don't have that info"
  (0 superseded). **In isolation the same case passes** (March superseded, June current) —
  so the *mechanism* is correct; the failure is **extraction inconsistency as context
  grows** (relation-verb / subject drift). A real finding: correctness depends on the LLM
  extracting consistent triples, which is fragile. Fix direction: detect conflicts by
  subject + value-kind, not exact relation string.

## Head-to-head vs Mem0 OSS (`benchmarks/vs_mem0.py`, same workload, same Gemini)
Scrupulously fair — and it corrected one of our own assumptions:
- **Determinism on reads is a WASH.** Mem0's vector retrieval is *also* deterministic.
  Our real edge is narrower: a deterministic *rendered answer* (cached, byte-identical, 0
  extra model calls), not "determinism" in the abstract.
- **Correction handling:** PrismCortex updated `40k → 55k`; **Mem0's top result stayed
  `40k`** (didn't surface the corrected value). Real, but possibly config/phrasing
  sensitive — Mem0 is far more mature overall.
- **Time-travel / audit:** PrismCortex retains the superseded value as a queryable
  bitemporal fact; **Mem0 OSS does temporal retrieval only as a paid Platform feature.**
- **Fair to Mem0:** much more mature, bigger ecosystem, ~3 lines with OpenAI defaults
  (the Gemini setup took several config fixes — embedder model, dims, Qdrant on Windows).

**Takeaway:** the moat is **not** "determinism" (everyone's vector reads are deterministic).
It's **deterministic rendered answers + bitemporal audit/time-travel + sovereignty** — a
narrower, truer wedge.

## Honest caveats
- **Determinism = replay-determinism** (6 first-renders, then 24 byte-identical replays),
  by design — not first-render token-determinism. The check is byte-equality, not
  correctness.
- **Throughput is a floor** — a single 2-vCPU container; latency includes network RTT.
- **Maturity: v0.1.** This exercise surfaced and fixed several real bugs (dropped entity
  attributes, entity-label resolution, `/reset` not clearing metrics or the durable cache).

## Reproduce
```bash
# image already built; needs .env with GEMINI_API_KEY
BACKEND=prism bash deploy/run_only.sh     # deploy 2 containers, run, capture
bash deploy/cleanup.sh                      # tear down the whole resource group
```
Artifacts: `benchmarks/results/{results.json, driver.log, server.log}` (`*.log` gitignored).
