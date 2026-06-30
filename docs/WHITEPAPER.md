# PrismCortex Whitepaper

**Compliance-grade agent memory — deterministic replay, bitemporal audit, self-hosted sovereignty**

Version 0.2.1 · Insight IT Solutions LLC · [insightits.com](https://www.insightits.com/products/prismcortex.html)

---

## Abstract

Enterprise AI agents fail compliance review because memory is implemented as append-only
chat logs or opaque vector retrieval in third-party SaaS. Answers drift, corrections
overwrite history, and auditors cannot reconstruct what the agent knew at a point in time.

**PrismCortex** is a self-hosted memory engine that **digests** conversation into a
bitemporal knowledge graph, **consolidates** uncertain facts in the background (biological
`sleep()`), and **recalls** by rendering facts once and freezing answers in a
content-addressed cache. The result: **byte-identical replay**, **time-travel audit**,
and **corrections that retain history** — without sending production data to a memory vendor.

Validated on Azure with real Gemini: 24/24 deterministic replays, 99.6% cache hit rate,
zero server errors on the core path ([benchmarks/RESULTS.md](../benchmarks/RESULTS.md)).

---

## 1. The problem

| Failure mode | Why regulated buyers care |
|--------------|---------------------------|
| Append-only logs | No structured audit; grep is not evidence |
| Vector RAG drift | Similarity ≠ proof; corrections may not surface |
| Third-party memory SaaS | Data residency, subprocessors, legal review delays |
| "Temperature 0" claims | False for shared APIs; replay cannot be guaranteed |
| Unbounded context growth | Cost and latency scale with every chit-chat turn |

**Use cases PrismCortex targets:**

1. **Compliance-blocked agent launches** — legal needs replay certificates, not chat exports  
2. **Corrections with audit trail** — budget $40k→$55k; old value retained and queryable  
3. **Sovereign / air-gapped deployment** — offline license, no phone-home  
4. **Cost-efficient production** — salience-gated writes, ~99%+ cache hit on warm workloads  

---

## 2. Architecture

PrismCortex orchestrates five Insight ITS packages behind one API (`digest` / `recall`):

| Layer | Component | Role |
|-------|-----------|------|
| Projection | PrismLang | Deterministic text → embedding + taxonomy |
| Graph | PrismRAG | Bitemporal store, governed retrieval |
| Consolidation | PrismResonance | Salience, decay, `sleep()` |
| Cache + mesh | PrismLib | Content-addressed render cache, invalidation |
| **Orchestration** | **PrismCortex** | Staging buffer, versioning, determinism contract |

### Two-speed memory

```
ingest → salience gate → extract → route
         ├─ certain / urgent → commit inline (version++)
         └─ uncertain / conflict → staging buffer
                                        │
                              sleep() ──┘ consolidate → commit
```

**Fast path:** known facts and high-salience corrections commit immediately.  
**Slow path:** ambiguous or conflicting facts defer to labile staging; `sleep()` resolves
entity overlap, conflicts, and decay off the hot path.

### Bitemporal graph

Corrections **invalidate** old edges (`valid_to = now`) and **add** new edges — nothing
is destroyed. Auditors query superseded facts; `/recall_at` supports time-travel.

---

## 3. Determinism model (honest)

We do **not** claim shared-API token determinism. We claim **system-level replay determinism**:

| Tier | Mechanism | Guarantee |
|------|-----------|-----------|
| T0 | Content-addressed render cache | Byte-identical replay from render #2 |
| T1 | Extraction memoization | Idempotent re-digest of same input |
| T3 | Extractive facts | Numbers/names copied from graph, not generated |
| T4 | Verification pass | Rendered facts must match subgraph |

**Default product:** T0 + T1 + T3 + T4.

Cache key: `sha256(query ‖ subgraph@v ‖ template ‖ model_snapshot)`.  
A changed fact changes the subgraph hash → stale answers are unreachable.

**Scope:** replay-determinism with pinned model epoch; snapshot sources (not live feeds).

---

## 4. Enterprise capabilities (v0.2)

| Capability | API / feature |
|------------|---------------|
| Multi-tenant isolation | Per-tenant graph + cache paths |
| RBAC | Scoped API keys (read / write / admin / forget) |
| Explainability | `POST /explain` — evidence trail |
| Conflict surfacing | `GET /conflicts` — never silently serve contested facts |
| Time-travel | `POST /recall_at`, `GET /audit?at=` |
| Replay certificate | `GET /replay_certificate` |
| GDPR erasure | `POST /forget` + tombstones |
| Legal hold | `POST /legal_hold` |
| Audit console | `GET /console` |
| Scale (50k+ facts) | IVF ANN index (`PRISMCORTEX_USE_ANN=1`) |
| Observability | `/metrics`, `/dashboard`, structured JSONL logs |

---

## 5. Validation summary

### Azure E2E (real Gemini, v0.2.1)

| Claim | Result |
|-------|--------|
| Cross-container determinism | **PASS** — 24/24 byte-identical |
| Reconsolidation | **PASS** — $40k→$55k, history retained |
| Conflict resolution | **PASS** — staged→`sleep()` |
| Memory plateau | **PASS** — 675 turns, 0 new edges |
| Cache hit rate | **99.57%** (30 Gemini / 2,563 recalls) |
| Cached replay latency | **~6 ms** vs **~724 ms** first render |
| Mixed load @ c=20 | **0 errors** |
| Server errors | **0** |

### Scale (ANN, no LLM)

| Facts | hit@8 | retrieve p95 |
|-------|-------|--------------|
| 10,000 | 91.5% | 10 ms |
| 50,000 | 85.0% | 74 ms |

Full artifacts: [benchmarks/RESULTS.md](../benchmarks/RESULTS.md), [scale_ann.json](../benchmarks/results/scale_ann.json).

---

## 6. Deployment models

### A. Python library (in-process)

```python
from prismcortex import reference_memory
mem = reference_memory()
mem.digest("Our deploy budget is $40,000.")
print(mem.recall("What is our deploy budget?").answer)
```

### B. HTTP service (multi-agent, any language)

```bash
pip install "prismcortex[gemini,server]"
uvicorn prismcortex.server:app --host 0.0.0.0 --port 8080
```

Docker image included; Azure ACI deploy scripts in `deploy/`.

---

## 7. Licensing & commercial model

**Open-core (MIT):** core `digest`/`recall`, bitemporal graph, determinism cache.

**Commercial (offline Ed25519 license):** audit console, advanced governance, scale tiers,
sovereign determinism options. No phone-home — required for air-gapped regulated buyers.

See [DESIGN.md](../DESIGN.md) §7, [docs/SLA.md](SLA.md), [docs/SOC2_ROADMAP.md](SOC2_ROADMAP.md).

---

## 8. Comparison positioning

| Dimension | Vector RAG / Mem0-style | PrismCortex |
|-----------|-------------------------|-------------|
| Storage | chunks / embeddings | bitemporal graph gist |
| Corrections | may not surface | invalidate + retain history |
| Determinism on reads | retrieval deterministic | **rendered answer** frozen + replayable |
| Audit | search results | evidence trail + replay certificate |
| Deployment | often SaaS | **self-hosted** default |
| Moat | ecosystem maturity | **audit + replay + sovereignty** |

Head-to-head scripts: `benchmarks/vs_mem0.py`, `benchmarks/vs_zep.py`.

---

## 9. Roadmap & maturity

**Technology:** v0.2.1 — enterprise stack landed, Azure-validated core claims.  
**Product:** pilot-ready for regulated design partners; pen-test and SOC 2 Type I in progress.  
**Not claimed:** hosted production SaaS for PHI/PII; 50 concurrent clients per node without tuning.

See [ROADMAP.md](../ROADMAP.md).

---

## 10. References

- **AI agent handoff:** [AGENTS.md](../AGENTS.md) — URLs, address, processes for automation  
- **GitHub:** https://github.com/insightitsGit/PrismCortex *(public)*  
- Product page: https://www.insightits.com/products/prismcortex.html  
- PyPI: https://pypi.org/project/prismcortex/  
- Design spec: [DESIGN.md](../DESIGN.md)  
- Benchmarks: [benchmarks/RESULTS.md](../benchmarks/RESULTS.md)  
- Security: [SECURITY.md](../SECURITY.md)  
- Contact: info@insightits.com · +1 (973) 692-6919 · Insight IT Solutions LLC  
- Address: 39 Aliso Ridge Loop, Mission Viejo, CA 92691, US  

---

*© Insight IT Solutions LLC. MIT license for OSS core components.*
