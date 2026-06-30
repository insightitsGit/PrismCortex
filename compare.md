# PrismCortex — Comparison & landing page spec

> **Audience:** AI agents and humans building the **insightits.com/products/prismcortex** landing page.  
> **Goal:** Add an honest “How we compare” section vs Mem0, Zep, and generic vector RAG.  
> **Engineering detail:** [docs/COMPETITIVE.md](docs/COMPETITIVE.md) · **GTM copy:** [infoAlex.md](infoAlex.md)  
> **GitHub:** https://github.com/insightitsGit/PrismCortex

---

## 0. Positioning in one sentence

**Mem0 and Zep win published accuracy benchmarks; PrismCortex wins compliance — byte-identical replay, bitemporal audit, and self-hosted sovereignty.**

Do not claim “we beat Mem0 on LoCoMo” until a **full** LoCoMo run is published. Lead with **differentiation**, cite competitor numbers as **reference**.

---

## 1. Suggested landing page section: “How we compare”

Place after **Proof bar** and before **Pricing** (see [infoAlex.md](infoAlex.md) §9).

### Section title options

- How PrismCortex compares
- Built for compliance, not just recall
- Memory your auditors can trust — vs the alternatives

### Subhead (pick one)

- Same Gemini, same correction test — different outcomes on audit and replay.
- Mem0 and Zep optimize accuracy at scale. We optimize **replay, audit, and sovereignty**.

---

## 2. Comparison table (safe for website)

Use this table on the product page. Footnote competitor LoCoMo/LongMemEval as *their published benchmarks*.

| | **Vector RAG / chat log** | **Mem0** | **Zep** | **PrismCortex** |
|---|---------------------------|----------|---------|-----------------|
| **Primary pitch** | Similarity search | Mature agent memory + SaaS | Temporal graph memory (SaaS) | **Compliance-grade memory** |
| **LoCoMo accuracy** | N/A | **91.6%** *(published)* | — | Full run pending *(smoke: 66.7% partial)* |
| **LongMemEval** | N/A | **94.8%** *(published)* | +18.5% vs baseline *(paper)* | Full run pending |
| **Correction surfaces new value** | Unreliable | Varies *(our test: top hit stale)* | Strong *(graph)* | **Yes** *(live test)* |
| **Old facts auditable** | No | Platform feature / varies | Yes *(graph)* | **Yes** *(OSS bitemporal)* |
| **Byte-identical answer replay** | No | No | No | **Yes** *(24/24 Azure)* |
| **Cached recall latency** | Varies | ~0.9–1.1 s p50 | ~200 ms *(marketing)* | **~6 ms** |
| **Cache hit rate (warm)** | — | — | — | **99.6%** |
| **Self-hosted default** | Sometimes | OSS + Platform SaaS | No | **Yes** |
| **Evidence trail / replay cert** | No | Limited | Graph context | **`/explain`, `/replay_certificate`** |

**Footnote copy:**

> Mem0 scores from [mem0.ai/research](https://mem0.ai/research) (Apr 2026). Zep from [arxiv.org/abs/2501.13956](https://arxiv.org/abs/2501.13956). PrismCortex Azure + head-to-head from [benchmarks/results/competitive/](benchmarks/results/competitive/) (Jun 2026).

---

## 3. Live head-to-head: correction test ($40k → $55k)

**Reproducible.** Same fact, correction, query. Real Gemini on both (see `benchmarks/results/competitive/vs_mem0.json`):

| Result | PrismCortex | Mem0 OSS |
|--------|-------------|----------|
| After correction, shows **$55k** | **Yes** | **No** (top retrieval stayed $40k) |
| Old **$40k** still in audit trail | **Yes** | Yes (in store) |
| Identical answer on replay | **Yes** (cache hit) | N/A (returns memory text) |

**Website callout (short):**

> We ran the same correction test as our Mem0 comparison: budget **$40k → $55k**. PrismCortex surfaced the new value and kept the old fact for audit. Mem0’s top retrieval stayed on $40k in our live OSS run.

**Do not say:** “Mem0 can’t handle corrections” — they report **96.2% knowledge-update** on LongMemEval. Say: *our narrow retrieval test* vs *their benchmark suite*.

---

## 4. Azure proof bar (reuse on page)

Already validated — safe to show as icons/numbers:

| Stat | Value |
|------|-------|
| Deterministic replay | **24/24** byte-identical |
| Cache hit rate | **99.6%** |
| Cached replay vs first render | **~6 ms** vs **~724 ms** |
| Mixed load @ 20 concurrent clients | **0 errors** |
| Server errors (core path) | **0** |
| Reference sizing | **~20 clients / 4 vCPU node** |

Source: [benchmarks/RESULTS.md](benchmarks/RESULTS.md)

---

## 5. Differentiation bullets (for feature grid)

Copy-paste friendly:

- **Byte-identical replay** — same query + memory version → same answer bytes (24/24 on Azure).
- **Bitemporal audit** — corrections invalidate but **retain** history; time-travel via `/recall_at`.
- **Evidence, not chunks** — `/explain` returns fact + source trail; `/replay_certificate` for auditors.
- **Self-hosted sovereignty** — your VPC, offline license, no memory SaaS for production PHI/PII.
- **Cost story** — 99.6% cache hit; ~30 Gemini calls for 2,500+ recalls in benchmark.

---

## 6. Where competitors lead (honest — optional accordion)

Use an “Industry context” or FAQ accordion so legal/compliance buyers trust you:

| They lead on | Say this |
|--------------|----------|
| LoCoMo / LongMemEval leaderboard | Mem0 publishes **91.6% / 94.8%** — industry reference for accuracy |
| Managed SaaS + SDK maturity | Mem0 Platform, Zep Cloud — faster time-to-hello-world |
| Long-context BEAM (1M+ tokens) | Mem0 BEAM benchmark — not our focus yet |
| Ecosystem (21+ integrations) | Mem0 — we’re early; Python + HTTP API today |

---

## 7. Do / don’t on the website

### Do say

- “Validated on Azure with real Gemini — zero server errors on the core path.”
- “Mixed read/write at **20 concurrent clients, 0 errors** on a single 4 vCPU node.”
- “**Self-hosted** production; hosted **30-day validation trial** for evaluation only.”
- “Reproducible benchmarks on GitHub.”

### Do not say

- “We beat Mem0 on LoCoMo” *(full run not published)*  
- “50 concurrent clients per node, zero failures” *(stress test @ c=50 still has client timeouts)*  
- “SOC 2 certified” *(Type I in progress)*  
- “Hosted production for regulated PHI/PII” *(trial sandbox only)*

---

## 8. Page blocks to add (checklist for site agent)

- [ ] **Comparison table** (§2) — desktop table + mobile stacked cards  
- [ ] **Correction callout** (§3) — mini case study: $40k → $55k  
- [ ] **Proof bar** (§4) — reuse 24/24 · 99.6% · 6 ms · 0 errors  
- [ ] **“Who this is for”** — regulated B2B (finance, health, legal, insurance)  
- [ ] **Link to GitHub** — https://github.com/insightitsGit/PrismCortex  
- [ ] **Link to PyPI** — https://pypi.org/project/prismcortex/  
- [ ] **CTA** — Start 30-Day Validation · View benchmark proof  

Match layout to [prismrag.html](https://www.insightits.com/products/prismrag.html). Colors: `#0f1419` bg, `#5b9bd5` accent (see `prismcortex/static/index.html`).

---

## 9. SEO / meta suggestions

- **Title suffix:** Compliance-Grade Agent Memory | Compare vs Mem0 & Zep  
- **Keywords:** agent memory comparison, auditable AI memory, Mem0 alternative self-hosted, bitemporal agent memory, deterministic agent replay  

---

## 10. Source files for the site agent

| Asset | Path |
|-------|------|
| Comparison summary JSON | `benchmarks/results/competitive/competitive_summary.json` |
| vs Mem0 live run | `benchmarks/results/competitive/vs_mem0.json` |
| vs Zep (PrismCortex side) | `benchmarks/results/competitive/vs_zep.json` |
| LoCoMo smoke | `benchmarks/results/competitive/locomo-smoke/` |
| Full competitive doc | `docs/COMPETITIVE.md` |
| Azure scorecard | `benchmarks/RESULTS.md` |
| Load / sizing honesty | `docs/LOAD_BENCHMARK.md`, `docs/SLA.md` |
| Landing page GTM | `infoAlex.md` |

---

## 11. Sales one-liner (hero alternative)

> **Agent memory your auditors can actually trust** — byte-identical replay, bitemporal audit, self-hosted. Validated on Azure; reproducible on GitHub.

---

*Last updated: 2026-06-30 · Insight IT Solutions LLC · info@insightits.com*
