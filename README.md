# PrismCortex

[![PyPI](https://img.shields.io/pypi/v/prismcortex)](https://pypi.org/project/prismcortex/)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/prismcortex)](https://pypi.org/project/prismcortex/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub](https://img.shields.io/github/stars/insightitsGit/PrismCortex?style=social)](https://github.com/insightitsGit/PrismCortex)

> **Deterministic, bitemporal memory & execution engine for multi-turn AI agents.**
> Stop agent memory decay, stale vector collisions, indirect prompt injection, and
> non-deterministic hallucination loops in production RAG systems.

**Repository:** https://github.com/insightitsGit/PrismCortex *(public)* · **Package:** [`prismcortex` 0.4.1](https://pypi.org/project/prismcortex/0.4.1/)

**Author:** Amin Parva · **Company:** [Insight IT Solutions LLC](https://www.insightits.com) · [www.insightits.com](https://www.insightits.com)

[AI agent handoff](AGENTS.md) · [Whitepaper](docs/WHITEPAPER.md) · [Use cases](docs/USE_CASES.md) · [Benchmarks](benchmarks/RESULTS.md) · [How we compare](compare.md) · [Design](DESIGN.md)

**Product page:** [insightits.com/products/prismcortex](https://www.insightits.com/products/prismcortex.html)

---


**Keywords:** agent memory, gist graph, bitemporal memory, citation verifier, byte-identical replay, PrismCortex, LLM memory plateau, constraint compiler for agents

### Production failure modes we solve

If agentic systems are hitting any of these enterprise walls, PrismCortex provides native middleware abstractions:

| Failure mode | What we ship |
|--------------|--------------|
| **Indirect prompt injection** | Sanitize retrieved payloads before they reach the LLM — `prismcortex.sanitizer` |
| **Stale policy invalidation** | Bitemporal state separates event time from ingestion time — `prismcortex.determinism` |
| **Hallucinated citations** | Entailment verifier checks claim-to-memory alignment — `prismcortex.verifier` |
| **Numeric filter breakdown** | NL bounds (`"< 30 days"`, `"over $50k"`) → DB constraints — `prismcortex.constraints` |

Also covered by the core engine: context decay / anaphora loss, multi-hop blindness, and non-reproducible replays (see below).

---

### Enterprise services & commercial support

Building high-risk agent workflows, enterprise RAG data layers, or bitemporal compliance audits?

- **Documentation & benchmarks:** [docs/USE_CASES.md](docs/USE_CASES.md) · [docs/COMPETITIVE.md](docs/COMPETITIVE.md) · [benchmarks/RESULTS.md](benchmarks/RESULTS.md)
- **Product & pricing:** [insightits.com/products/prismcortex](https://www.insightits.com/products/prismcortex.html)
- **Architecture & implementation consulting:** [info@insightits.com](mailto:info@insightits.com) · +1 (973) 692-6919 · [www.insightits.com](https://www.insightits.com)

---

## Why standard RAG memory fails

| Failure mode | What goes wrong in production |
|--------------|-------------------------------|
| **Stale knowledge collisions** | Naive vector similarity returns superseded policies alongside active ones — the agent cites both. |
| **Context decay & anaphora loss** | Parent entity subject is lost across multi-turn sessions; “it / that / the policy” no longer resolve. |
| **Multi-hop blindness** | Continuous vector spaces fail at logical dependency joins (A→B→C) that a graph can walk. |
| **Non-reproducible replays** | You cannot prove byte-identical state for audit — temperature-0 LLM calls still drift. |

---

## How PrismCortex fixes it

| Capability | Where it lives | What you get |
|------------|----------------|--------------|
| **Bitemporal auditing** | `determinism.py`, graph edges (`valid_from` / `valid_to`) | Separates real-world event time from ingestion/system time; corrections soft-invalidate, never erase. |
| **Causal graph links** | `engine.py`, `tests/test_graph_engine.py` | Extracted facts become relational edges — not isolated float arrays. |
| **Salience & consolidation** | `salience.py`, `Memory.sleep()` | Skips low-value turns; parks uncertain facts; consolidates without dropping history. |
| **Byte-identical replay** | content-addressed cache + `/replay_certificate` | Reproducible answer audits for SOC 2–aligned / compliance workflows. |
| **Injection defense** | `sanitizer.py` | Strip prompt-hijack payloads from recalled context before render. |
| **Citation check** | `verifier.py` | Non-LLM 0..1 entailment score (claim vs memory span). |
| **NL → DB filters** | `constraints.py` | Numeric/date bounds → JSON + pgvector SQL (vendor adapters: see [ROADMAP](ROADMAP.md)). |

**API surface (real):** `digest()` → graph · `recall()` → frozen answer · `sleep()` → consolidate · `explain()` → evidence.

Known limits (multi-modal bytes, Pinecone/Qdrant/Milvus push-down): [ROADMAP — Post-0.4.0 edge cases](ROADMAP.md#post-040-edge-cases-future-releases).

---

## 5-line quickstart

```python
from prismcortex import reference_memory

mem = reference_memory()  # GEMINI_API_KEY for real extraction
mem.digest("California parental leave updated to 12 weeks.")
print(mem.recall("What is our CA leave policy?").answer)
# Correction keeps history: digest a change → recall new value; old edge retains valid_to.
```

Zero-dependency demo (no API key — rule-based extractor):

```bash
python examples/quickstart.py
```

With real Gemini:

```bash
pip install "prismcortex[gemini]"
GEMINI_API_KEY=... python examples/quickstart.py
```

---

## Competitive positioning

Mem0 / Zep lead **published accuracy** suites (LoCoMo, LongMemEval). PrismCortex leads **compliance** — temporal audit, consolidation, causal graph, and byte-identical replay. Do not claim LoCoMo wins until a full PrismCortex run is published.

| Capability | Naive vector RAG | Mem0 / Zep | **PrismCortex** |
|------------|------------------|------------|-----------------|
| **Temporal auditing** | No (append / re-rank) | Platform / graph varies | **Yes** — OSS bitemporal edges |
| **Execution replay** | No | No byte-identical answers | **Yes** — 24/24 Azure E2E |
| **Memory consolidation** | Truncate / summarize | Product features vary | **Yes** — salience + `sleep()` |
| **Causal graph engine** | Flat embeddings | Zep: temporal graph; Mem0: memory store | **Yes** — relation edges + evidence |

Live correction head-to-head (same Gemini): PrismCortex surfaced **$55k** after **$40k → $55k**; Mem0 OSS top retrieval stayed **$40k** in our run — [vs_mem0.json](benchmarks/results/competitive/vs_mem0.json).

Full tables: [compare.md](compare.md) · [docs/COMPETITIVE.md](docs/COMPETITIVE.md)

---

## Validated claims (Azure E2E, real Gemini, v0.2.1)

| Claim | Result |
|-------|--------|
| Replay determinism | **24/24** byte-identical |
| Corrections + audit | **$40k → $55k**; superseded fact retained |
| Cache | **99.6%** hit — 30 Gemini / 2,563 recalls |
| Cached replay | **~6 ms** vs **~724 ms** first render |
| Mixed load (c=20) | **0 errors** on 4 vCPU · `slo_pass: true` |
| Scale (50k facts, ANN) | **85% hit@8**, **74 ms** p95 |

Details: [benchmarks/RESULTS.md](benchmarks/RESULTS.md)

---

## Install

```bash
pip install prismcortex                  # core (MIT)
pip install "prismcortex[gemini]"        # + real Gemini extraction/rendering
pip install "prismcortex[prism]"         # + Insight ITS stack with prismlib
pip install "prismcortex[prism-plus]"    # + same stack with prismlib-plus
pip install "prismcortex[server]"        # + FastAPI HTTP service
```

Requires **Python 3.10+**. `[prism]` and `[prism-plus]` are mutually exclusive.

### HTTP service

```bash
export GEMINI_API_KEY=...
export PRISMCORTEX_API_KEY=your-secret
uvicorn prismcortex.server:app --host 0.0.0.0 --port 8080
# OpenAPI: http://localhost:8080/docs
```

### What's new in 0.4.1

- SEO / lead-gen README refresh on PyPI (same code as 0.4.0)
- Documented post-0.4.0 roadmap gaps (multi-modal + vendor vector filters)

### What's new in 0.4.0

- **`ConstraintCompiler`** — NL → JSON / PostgreSQL filters for numeric & date bounds
- **`CorpusSanitizer`** — strip prompt-injection payloads before LLM context
- **`CitationVerifier`** — non-LLM 0..1 entailment score for recalled facts vs answers
- Wired into `Memory.recall` (`sanitize_retrieval`, `extract_constraints`, `verify_citations`)
- Release notes: [docs/CHANGELOG_0.4.0.md](docs/CHANGELOG_0.4.0.md)

### What's new in 0.3.0

- `mem.on_event(callback)` — correction / conflict / forget (`MemoryEvent`)
- Evidence fields: `valid_from`, `supersedes_prior`, `prior_value`
- `[prism-plus]` extra — see [docs/CHANGELOG_0.3.0.md](docs/CHANGELOG_0.3.0.md)

---

## Architecture

```
digest(text) ─▶ salience gate ─▶ extract gist ─▶ delta in RAM
                   ├─ certain / urgent ─▶ commit  (version++)
                   └─ uncertain ───────▶ staging ──▶ sleep() ──▶ commit

recall(query) ─▶ retrieve subgraph ─▶ cache hit? replay (byte-identical)
                                    └─ miss? render once → freeze
```

Determinism claim (honest): we do **not** claim temperature-0 LLM identity. We claim **replay** identity after first render for a `(query, memory-version)` pair. See [DESIGN.md](DESIGN.md).

---

## Development

```bash
git clone https://github.com/insightitsGit/PrismCortex.git
cd PrismCortex
pip install -e ".[dev,gemini,server]"

pytest tests/                          # graph tests need no API key
GEMINI_API_KEY=... pytest              # full suite
python examples/quickstart.py          # zero-deps path
python benchmarks/scale_bench.py --ann
```

Azure E2E / load driver (needs running server): `python benchmarks/driver.py` — see [docs/OPS_RUNBOOK.md](docs/OPS_RUNBOOK.md).

---

## Documentation

| Doc | Contents |
|-----|----------|
| [AGENTS.md](AGENTS.md) | Canonical URLs, contacts, processes |
| [docs/USE_CASES.md](docs/USE_CASES.md) | Problem → architecture mappings |
| [docs/WHITEPAPER.md](docs/WHITEPAPER.md) | Product whitepaper |
| [DESIGN.md](DESIGN.md) | Engineering design |
| [benchmarks/RESULTS.md](benchmarks/RESULTS.md) | Azure scorecard |
| [compare.md](compare.md) / [docs/COMPETITIVE.md](docs/COMPETITIVE.md) | Market comparison |
| [docs/CAPACITY.md](docs/CAPACITY.md) / [docs/LOAD_BENCHMARK.md](docs/LOAD_BENCHMARK.md) | Sizing & load SLO |
| [SECURITY.md](SECURITY.md) | Security posture |

---

## Licensing

**Open-core (MIT):** `digest` / `recall`, bitemporal graph, determinism cache — free on PyPI.

**Commercial:** audit console, advanced governance, scale tiers — offline Ed25519 key, no phone-home.

Enterprise: [info@insightits.com](mailto:info@insightits.com) · +1 (973) 692-6919 · [Insight IT Solutions LLC](https://www.insightits.com) · [www.insightits.com](https://www.insightits.com)

**Author:** Amin Parva ([insightits.info@gmail.com](mailto:insightits.info@gmail.com))

---

## Links

- Author: **Amin Parva** ([insightits.info@gmail.com](mailto:insightits.info@gmail.com))
- Company: [https://www.insightits.com](https://www.insightits.com)
- GitHub: https://github.com/insightitsGit/PrismCortex
- PyPI: https://pypi.org/project/prismcortex/
- Product page: https://www.insightits.com/products/prismcortex.html
