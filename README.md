# PrismCortex

**Deterministic, auditable, self-consolidating memory for AI agents.**

Most agent "memory" is an append-only chat log that you stuff back into the context
window until it overflows. PrismCortex does what a brain does instead: it **digests**
each turn into a knowledge graph, **consolidates** uncertain facts in the background
(like sleep), and demotes the LLM from *thinker* to *renderer* — it only paints the
facts you hand it. Change the memory and only the affected answers change; everything
is traceable to the exact facts and source events behind it.

It's the orchestration layer over five shipped Insight ITS packages — PrismLang,
PrismRAG, PrismResonance, PrismLib, and Chorus Fabric — behind one tiny API.

```python
from prismcortex import reference_memory

mem = reference_memory(cache_path=".prismcortex_cache/demo.json")

mem.digest("My production deploy budget is $40,000.")
print(mem.recall("What's my deploy budget?").answer)        # → "$40,000"

mem.digest("Correction: my deploy budget is now $55,000.")  # fast-tracked (ALERT)
print(mem.recall("What's my deploy budget?").answer)        # → "$55,000"
# …and the $40,000 fact is still on record, time-stamped, for audit/time-travel.
```

## Why it's different

| | Append-only RAG | PrismCortex |
|---|---|---|
| Storage | every chat turn | graph topology (the *gist*) |
| Updates | append + hope retrieval ranks it | bitemporal: invalidate old, add new, keep history |
| Determinism | none (logs + LLM both drift) | content-addressed render cache, replay-identical |
| Cost | re-extract context every call | salience-gated writes, cached reads |
| Audit | grep the logs | every answer → exact facts + source events |

## What you get that a vector store can't

| Capability | What it does |
|---|---|
| **Explainability** (`/explain`) | Every answer returns its **evidence trail** — the exact facts, their source events, and confidence. A vector store returns memories; only a provenance graph returns *evidence*. |
| **Confidence + freshness** | Each recall reports how reinforced its facts are (0–1) and when they were last confirmed. |
| **Time-travel / audit** | Corrections invalidate but **retain** the old fact as a queryable bitemporal record (a paid feature in Mem0 OSS). |
| **Bounded memory** | `sleep()` prunes the coldest facts to a cap — the active set **plateaus** instead of growing forever; pruned facts are kept for audit. |
| **~12× smaller index** | 128-dim vectors vs the 1536–3072-dim default elsewhere; plus entity-dedup. |
| **Sovereign** | Self-hosted, your data, offline-keyed — no third-party SaaS. |

These are validated in `benchmarks/` (incl. a fair head-to-head vs Mem0 in `vs_mem0.py`).

## Determinism, honestly

We do **not** claim "temperature 0 → identical output" — that's false for any shared
API model (batching + floating-point non-associativity flip near-tied tokens). Instead:

- **Content-addressed rendering.** The cache key is a hash of the exact retrieved
  subgraph + query + template + **pinned model snapshot**. The model is invoked at most
  once per unique (query, memory-version); its answer is frozen and replayed
  byte-for-byte. A changed fact changes the key, so a stale answer is *unreachable* —
  invalidation and determinism are the same mechanism.
- **Extractive facts.** Numbers, names, ids, and dates are substituted from the graph,
  not generated, and a verification pass rejects fabricated values — so the *facts* are
  deterministic even on the first render; only prose phrasing can vary (then it's frozen).

Scope: replay-determinism, pinned model snapshot, snapshot sources (not live feeds).
First-render *token* determinism requires the self-hosted sovereign tier. See
[`DESIGN.md`](DESIGN.md) §2.

## Architecture (one engine, five swappable ports)

```
digest(text) ─▶ salience gate ─▶ extract gist ─▶ delta in RAM
                                                   ├─ certain / urgent ─▶ commit  (version++)
                                                   └─ uncertain ───────▶ staging buffer
                                                                              │ sleep()
                                                                       consolidate ─▶ commit (version++)

recall(query) ─▶ retrieve subgraph @version ─▶ content-address ─▶ cache hit? replay
                                                                  miss? render once → freeze
```

| Port | Reference adapter | Production (`pip install prismcortex[prism]`) |
|---|---|---|
| Gist projection | hashing-trick embeddings | `prismlang` |
| Graph store (bitemporal) | in-memory | `prismrag-patch` |
| Weight / salience / sleep | in-process | `prismresonance` |
| Render cache (durable) | JSON file | `prismlib` (cache-as-failover) |
| Mesh broadcast | in-process | `prismlib` cluster / Chorus |
| Extraction + rendering | — | **real Gemini** (`prismcortex[gemini]`) |

## Install & test

```bash
pip install -e .                      # core
pip install -e ".[gemini]"            # + real Gemini extraction/rendering

pytest tests/test_graph_engine.py     # deterministic substrate — no API key
GEMINI_API_KEY=... pytest             # full end-to-end with real Gemini
```

## Licensing

Open-core (MIT). The core (`digest`/`recall`, bitemporal graph, determinism cache) is
free. Commercial modules (audit console, consolidation-at-scale, multi-agent mesh, the
sovereign determinism tier) are gated by an **offline signed license key** — no
phone-home, works air-gapped. See [`DESIGN.md`](DESIGN.md) §7.
