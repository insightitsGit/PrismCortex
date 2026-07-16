# PrismCortex — competitive comparison

Honest positioning vs Mem0, Zep, and standard memory benchmarks.  
Evidence links below — re-run scripts to refresh numbers.

**Related:** [LOAD_BENCHMARK.md](LOAD_BENCHMARK.md) · [benchmarks/RESULTS.md](../benchmarks/RESULTS.md) · [AGENTS.md](../AGENTS.md)

---

## 1. Two comparison layers

| Layer | What it measures | Our scripts |
|-------|------------------|-------------|
| **Standard accuracy** | LoCoMo, LongMemEval (same methodology as Mem0) | `benchmarks/competitive/run_standard.py` |
| **Differentiation** | Correction, audit, replay, sovereignty | `benchmarks/vs_mem0.py`, `benchmarks/vs_zep.py` |
| **Ops / capacity** | Latency, load, cache (Azure E2E) | [benchmarks/RESULTS.md](../benchmarks/RESULTS.md) |

Do **not** compare Azure throughput to Mem0 LoCoMo scores — different axes.

---

## 2. Published market numbers (reference)

Sources: [Mem0 research](https://mem0.ai/research), [Mem0 GitHub](https://github.com/mem0ai/mem0), [Zep paper](https://arxiv.org/abs/2501.13956) (Jan 2025).

| Product | LoCoMo | LongMemEval | BEAM (1M) | Retrieval latency | Deployment |
|---------|--------|-------------|-----------|-------------------|------------|
| **Mem0** (Apr 2026 algo) | **91.6%** | **94.8%** | **64.1%** | ~0.88–1.09 s p50 | SaaS + OSS |
| **Zep** | — | +18.5% vs full-context (paper) | — | ~200 ms (marketing) | Managed SaaS |
| **PrismCortex** | *run below* | *run below* | not run | **~6 ms** cache replay (Azure) | Self-hosted default |

Mem0 LongMemEval **knowledge update** category: **96.2%** (their docs).  
Mem0 BEAM **contradiction_resolution** @ 1M: **35.7%** (hard category for all vendors).

---

## 3. PrismCortex standard benchmarks (LoCoMo / LongMemEval)

Uses [mem0ai/memory-benchmarks](https://github.com/mem0ai/memory-benchmarks) prompts, datasets, and judge — with **PrismCortex** as memory backend and **Gemini** as answerer/judge.

### Setup (once)

```bash
bash scripts/setup_bench_vendor.sh          # or scripts/setup_bench_vendor.ps1
pip install -e ".[gemini,competitive]"
```

### Smoke (quick sanity)

```bash
GEMINI_API_KEY=... python benchmarks/competitive/run_standard.py locomo \
  --project-name pc-locomo-smoke \
  --conversations 0 \
  --max-questions 5 \
  --output-dir benchmarks/results/competitive/locomo-smoke
```

### Full run (expensive — full conversation ingest + ~1,540 LoCoMo questions)

```bash
GEMINI_API_KEY=... python benchmarks/competitive/run_standard.py locomo \
  --project-name pc-locomo-full \
  --output-dir benchmarks/results/competitive/locomo-full

GEMINI_API_KEY=... python benchmarks/competitive/run_standard.py longmemeval \
  --project-name pc-lme-full \
  --all-questions \
  --output-dir benchmarks/results/competitive/longmemeval-full
```

Results land under `benchmarks/results/competitive/<project>/` as JSON + metrics.

### Smoke run (PrismCortex, 2026-06-30 — partial ingest, not comparable to Mem0 full)

Limited ingest (`PRISM_BENCH_INGEST_LIMIT=40`, conversation 0 only, 3 questions):

| Cutoff | Overall | Notes |
|--------|---------|-------|
| top_10 | **0%** (0/3) | Too few facts ingested |
| top_20 | **33%** (1/3) | |
| top_200 | **66.7%** (2/3) | open-domain 100%, temporal 50% |

Artifact: `benchmarks/results/competitive/locomo-smoke/locomo_results_*.json`

**Full LoCoMo** (~1,540 questions, 419 chunks × 10 conversations) requires overnight run + significant Gemini cost. Compare to Mem0 **91.6%** only after full run.

### Methodology note

- Memory **search** returns **graph facts** (not PrismCortex rendered answers) — fair comparison to Mem0 retrieval → answerer → judge.
- Ingest calls `digest()` per message chunk → **real Gemini extraction** (costly, same order of magnitude as Mem0 OSS ingest).
- Use `PRISM_BENCH_INGEST_LIMIT=N` for smoke runs only; remove for full benchmark.

---

## 4. Head-to-head: correction workload ($40k → $55k)

Same fact, correction, and query on both systems. Real Gemini on both sides for Mem0.

```bash
GEMINI_API_KEY=... python benchmarks/vs_mem0.py
GEMINI_API_KEY=... ZEP_API_KEY=... python benchmarks/vs_zep.py
```

Artifacts: `benchmarks/results/competitive/vs_mem0.json`, `vs_zep.json`

**Live run (2026-06-30, real Gemini) — see `vs_mem0.json`:**

| Dimension | PrismCortex | Mem0 OSS | Zep (needs `ZEP_API_KEY`) |
|-----------|-------------|----------|---------------------------|
| Correction surfaces $55k | **Yes** | **No** (top hit stayed $40k) | Run live |
| Old $40k auditable | **Yes** (bitemporal) | Yes (in store) | Graph (paper) |
| Byte-identical render replay | **Yes** | N/A | N/A |
| Self-hosted default | **Yes** | OSS yes | **No** (SaaS) |

**Honest caveat:** Mem0 reports **96.2% knowledge-update** on LongMemEval — they handle corrections in their benchmark design. Our narrow script tests one-shot vector ranking on a single correction.

---

## 5. Where PrismCortex wins (evidence-backed)

| Claim | Evidence |
|-------|----------|
| Replay-deterministic **rendered** answers | Azure 24/24 — [RESULTS.md](../benchmarks/RESULTS.md) |
| Bitemporal audit in OSS core | vs_mem0.json, `/explain`, `/recall_at` |
| Reference load SLO (~20 clients) | `reference_slo_pass: true` — [LOAD_BENCHMARK.md](LOAD_BENCHMARK.md) |
| Cache economics | 99.57% hit, 30 Gemini / 2,563 recalls |
| Sovereignty | Self-hosted Docker, offline license |

---

## 6. Where competitors lead today

| Area | Leader |
|------|--------|
| Standard LoCoMo / LongMemEval leaderboard | **Mem0** (until we publish full runs) |
| Managed enterprise SaaS + SDK maturity | **Mem0 Platform**, **Zep** |
| Long-context BEAM (1M–10M tokens) | **Mem0** |
| Ecosystem integrations | **Mem0** (21+ frameworks) |

---

## 7. Sales-safe one-liner

> Mem0 and Zep publish strong **accuracy** on LoCoMo and LongMemEval. PrismCortex competes on **compliance**: byte-identical replay, bitemporal audit, and self-hosted sovereignty — plus standard benchmarks you can reproduce with `run_standard.py`.

---

## 8. Reproduce everything

```bash
# 1) Vendor + deps
bash scripts/setup_bench_vendor.sh
pip install -e ".[gemini,competitive,bench]"

# 2) Head-to-head
GEMINI_API_KEY=... python benchmarks/vs_mem0.py
GEMINI_API_KEY=... ZEP_API_KEY=... python benchmarks/vs_zep.py

# 3) Standard accuracy (smoke then full)
GEMINI_API_KEY=... python benchmarks/competitive/run_standard.py locomo \
  --project-name pc-smoke --conversations 0 --max-questions 5 \
  --output-dir benchmarks/results/competitive/locomo-smoke

# 4) Azure ops scorecard (separate)
BACKEND=prism bash deploy/run_only.sh
```

---

*Last updated: 2026-06-30 · Maintainer: Insight IT Solutions LLC*
