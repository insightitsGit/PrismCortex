# PrismCortex — use cases

How the engine maps production agent failures to concrete mechanisms.
Evidence: [benchmarks/RESULTS.md](../benchmarks/RESULTS.md) · Design: [DESIGN.md](../DESIGN.md)

**API:** `digest` / `recall` / `sleep` / `explain` / `recall_at` — not a fictional `MemoryEngine.remember()`.

---

## 1. Version control & stale policy invalidation

**Problem.** Naive vector RAG keeps embedding both “leave is 8 weeks” and “leave is 12 weeks.” Similarity returns whichever chunk is nearest — often the superseded one.

**PrismCortex approach**

1. `digest("… leave updated to 12 weeks")` extracts a relation edge.
2. A correction (`is_correction` / ALERT salience) **accommodates**: old edge gets `valid_to`, new edge is current.
3. `recall` only walks **current** edges; `explain` / history retain the prior value for audit.

**Why it works.** Bitemporal edges separate “what is true now” from “what was true then.” Vector stores have no first-class invalidation.

**Try it:** `python examples/quickstart.py` — correction `$40k → $55k` with superseded count.

---

## 2. Multi-hop relational dependencies via causal graphing

**Problem.** Continuous embeddings struggle with joins: *budget of the team that owns the DB in us-east-1*. Retrieval returns isolated sentences; the agent hallucinates the join.

**PrismCortex approach**

1. Extraction yields entities + **relations** (`hosted_in`, `budget_is`, …).
2. `recall` retrieves a subgraph and expands along edges (`_expand_subgraph` in `engine.py`).
3. Rendering answers from the joined subgraph, then freezes the prose in the content-addressed cache.

**Why it works.** Topology carries dependency structure that cosine similarity alone does not.

---

## 3. Multi-turn hallucination ratchet mitigation

**Problem.** Each turn appends chat text. Salience is flat. Low-value “ok thanks” still pollutes context; uncertain claims get treated as facts; errors compound across turns (the ratchet).

**PrismCortex approach**

| Mechanism | Module | Effect |
|-----------|--------|--------|
| Salience gate | `salience.py` | Skip / ALERT / EMERGENCY bands — no LLM on chit-chat |
| Staging | `ListStaging` + `Memory.sleep()` | Uncertain deltas park until consolidation |
| Idempotent digest | extraction memo in cache | Same text never re-extracted |
| Frozen recall | `determinism.content_address` | Same query + graph version → identical answer |

**Why it works.** Working memory is gated and consolidated; answers are not re-sampled every call.

---

## 4. Compliance & audit replays

**Problem.** Auditors ask: *What did the agent know on date D?* and *Prove this answer is reproducible.* Chat logs and SaaS memory rarely provide byte-identical certificates.

**PrismCortex approach**

| Need | Surface |
|------|---------|
| Evidence trail | `Memory.explain(query)` → `Evidence` (`valid_from`, `supersedes_prior`, `prior_value`) |
| Time-travel | `recall_at` / HTTP `POST /recall_at` |
| Replay proof | content-addressed cache; HTTP `GET /replay_certificate` |
| Erasure | `forget(source_id)` + tombstones |
| Events for caches | `on_event` → `MemoryEvent` (PrismShine / semantic cache eviction) |

**Validated (Azure E2E v0.2.1):** 24/24 byte-identical replays; correction with history retained — [RESULTS.md](../benchmarks/RESULTS.md).

**Honesty:** We claim **replay** determinism after first render, not identical live LLM draws at temperature 0.

---

## Related reading

- [WHITEPAPER.md](WHITEPAPER.md) — buyer narrative  
- [COMPETITIVE.md](COMPETITIVE.md) — Mem0 / Zep positioning  
- [PORTAL_AND_SITE_AGENT_PROMPT.md](PORTAL_AND_SITE_AGENT_PROMPT.md) — portal / site handoff  
