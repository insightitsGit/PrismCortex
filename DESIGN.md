# PrismCortex — Design Specification

> **Deterministic, auditable, self-consolidating memory for AI agents.**
> The memory *is* the graph's topology. Chats aren't stored — they're digested into
> graph mutations. The LLM is demoted from "thinker" to "renderer." Memory changes
> re-render only the answers they actually affect, and every answer is traceable to
> the exact facts and source events behind it.

PrismCortex is the orchestration product that ties five shipped Insight ITS packages
into a single memory engine. It owns two things none of them own individually: a
**bitemporal graph layer** and a **content-addressed determinism contract**.

---

## 1. The engine (owned IP, hidden behind one API)

| Role (biology) | Component | Function |
|---|---|---|
| Sensory filter | `prismlang` | Deterministic gist projection: text → vector envelope + taxonomy |
| Engram | `prismrag-patch` | Governed, hallucination-resistant retrieval over the graph |
| Synapse / consolidation | `prismresonance` | Weight, decay, salience bands, `sleep()` consolidation |
| Electrical sync | `prismlib` (cluster/CHORUS) | Broadcasts version bumps / cache invalidations |
| Durable answer store | `prismlib` (cache-as-failover) | Content-addressed, durable render cache |
| **Working memory + version contract** | **PrismCortex** | Labile staging buffer, bitemporal edges, graph versioning |

**Product principle:** the buyer never sees five libraries. They see one `Memory`
object with `digest()` and `recall()`. The five-package complexity is the moat,
hidden behind a trivial surface.

---

## 2. The determinism model (the honest version)

"temperature 0 → identical output" is **false** for any shared-API model (Gemini
included): dynamic cross-user batching + floating-point non-associativity perturb
logits enough to flip near-tied tokens; one flip reroutes the whole generation.
Temperature 0 removes sampling randomness, not numerical wobble.

We do not fight the model. We make determinism a property of the **system**, via a
stack of levers (dial the guarantee to the buyer's need):

| Tier | Lever | Guarantee | Cost |
|---|---|---|---|
| **T0** | Durable content-addressed render cache | Byte-identical replay from render #2 onward, forever | First render stochastic |
| **T1** | Extraction memoization (`hash(input ‖ extractor_model)`) | Re-digesting same input is idempotent; graph build is reproducible | — |
| **T2** | Constrained / schema decoding | Shrinks the surface where wobble can change meaning | Minor |
| **T3** | **Extractive facts** — load-bearing values (numbers, names, IDs, prices) are *substituted from the graph into a template*, never generated | **Facts are deterministic on the *first* render** (copied, not generated); only prose wobbles | — |
| **T4** | Verification pass (`prismrag-patch`) | Output facts must match the graph or regenerate → *factual* determinism even if lexical varies | One extra check |
| **T5** | Self-hosted batch-invariant inference (open weights + own GPUs) | True first-render token-determinism | Heavy infra; "sovereign tier" |

**Default product = T0 + T1 + T3 + T4.** This yields: *the meaning is deterministic
from render #1 (facts are copied from the graph), the wording is frozen from render #2
(cache), and every value is verified against and traceable to its source.* That is
what regulated buyers actually need. T5 is an enterprise upsell, not the default.

### Scope & limits (state these to buyers up front)
- Determinism is **replay-determinism**, scoped to a **pinned model snapshot**
  (`gemini-x.y-flash-NNN`, never a floating alias). A Google model rev correctly
  re-renders everything.
- The **first** render of a never-before-seen context is model-stochastic for *prose*
  (facts are not — see T3). Everything after is frozen.
- Concurrent first-renders of the same key need **single-flight locking** so two
  divergent answers can't race to freeze.
- Retrieval determinism requires PrismLang projection to be CPU-stable and ranking to
  use exact/stable ordering with **id tie-breaks** — not raw approximate-ANN order.
- Deterministic retrieval requires **snapshot sources**, not live feeds. A real-time
  API mixed into a multi-source "RAG lake" breaks reproducibility by definition.

---

## 3. Bitemporal graph (never destructive)

Biology's "overwrite bug" is a bug. Enterprises can't ship it. So we keep the gist-only
efficiency but add what biology lacks: immutable provenance and time-travel.

```
Node:  id, label, kind, embedding, attributes, weight, confidence, band, provenance
Edge:  id, src, dst, relation, weight, confidence,
       valid_from, valid_to (None = current), recorded_at, provenance, band
```

- **Assimilate** (new fact): add node/edge.
- **Accommodate** (correction): set old edge `valid_to = now`, add new edge
  `valid_from = now`. **Nothing is deleted.** → audit trail + "what did it believe
  last Tuesday?" time-travel.
- **Reinforce** (repetition): raise weight (LTP). A single contradicting mention
  lowers but does **not** instantly flip a 50×-reinforced fact.
- **Prune** (decay): soft — set `valid_to`, never destroy. Raw kept in cold storage.

---

## 4. Two-speed memory + sleep consolidation

Not every digestion decision is cheap. "Is this a correction? Same entity, different
name? Contradiction?" is expensive reasoning that must not block the request path.

**Fast path (in-request, RAM):**
1. **Known-check** against PrismLib cache: seen this exact input? (idempotent skip)
   entity already exists? (reinforce).
2. **Certain & simple** → commit inline, `version++`.
3. **High salience** (`EMERGENCY`/`ALERT` band) → fast-track commit even if it'd
   normally wait (flashbulb memory; amygdala salience accelerates consolidation).

**Working memory (labile staging buffer):**
4. **Uncertain / conflicting / needs-investigation** → write to staging, tagged with
   confidence + reason. **Does not touch the authoritative graph.** Provisional.

**Slow path (background job = `prismresonance.sleep()`):**
5. Drain staging off the hot path: entity resolution, conflict resolution, decay,
   pruning. Commit survivors as **one consolidation version**. Memoize conclusions
   so the same investigation never re-runs.

**Decay is event-driven, not wall-clock.** Weights change only at `sleep()` boundaries,
each producing a new immutable version. So memory is reproducible *within* a version
and "lives" in discrete heartbeats — which is both more biologically faithful and
what keeps the determinism contract intact.

```
new payload
   ├─▶ PrismLib known-check ─ seen? ─▶ idempotent skip / reinforce
   ├─▶ extract gist + salience band (PrismLang + Gemini)
   ├─ certain & simple ──────────▶ COMMIT inline → version++
   ├─ EMERGENCY / ALERT ─────────▶ COMMIT inline → version++   (flashbulb)
   └─ uncertain / conflicting ───▶ STAGING (labile, provisional)
                                        │
                              prismresonance.sleep()  ◀── background job
                                        │
                              resolve · merge · decay · prune
                                        │
                                  COMMIT consolidation → version++
```

By default, `recall()` reads **consolidated knowledge only** → fully deterministic.
A question about provisional info returns "not certain yet" until slept on. An
`include_provisional=true` mode can surface staged items flagged low-confidence for
agents that prefer responsiveness over strict determinism.

---

## 5. Lifecycles

**digest(payload):** known-check → salience gate (skip low-value turns; cost control) →
gist extract → delta calc in RAM → route (inline / staging) → commit + `version++` →
broadcast invalidation over mesh. Raw quarantined to cold storage, excluded from the
context path.

**recall(query):** project query (deterministic) → retrieve subgraph @ version
(exact/stable ranking) → build content-address
`key = sha256(query_proj ‖ canonical(subgraph@v) ‖ template_id ‖ model_id)` →
cache hit? replay bytes. miss? single-flight render (T3 extractive facts + T4 verify) →
freeze under key → return, with full provenance (node/edge ids, version, source events).

---

## 6. What changed vs the original (Gemini) design

| # | Original | PrismCortex |
|---|---|---|
| 1 | "temp 0 → identical output" (false) | Content-addressed cache + extractive facts + verification (true, layered) |
| 2 | Destructive overwrite / prune | Bitemporal, non-destructive (validity + provenance) |
| 3 | Single-speed RAM digest | Two-speed: fast inline + labile staging + sleep consolidation |
| 4 | Continuous decay | Discrete `sleep()`-boundary versioned consolidation |
| 5 | No salience control | Band-routing, flashbulb fast-track, salience gate (cost control) |
| 6 | Raw logs deleted | Quarantined cold storage, configurable retention |
| 7 | Chorus broadcasts writes | Chorus broadcasts version/invalidation; single source of truth |
| 8 | PrismResonance & PrismLib unused | Central: resonance = consolidation engine; PrismLib = durable store + mesh |
| 9 | One description per media file | Timecoded segment pointers (`asset_id + [t_start, t_end]`) |
| 10 | Determinism overclaimed | Explicit replay-determinism, pinned snapshot, snapshot-source boundary |

---

## 7. Packaging & licensing (open-core, self-hosted)

PrismCortex ships as a **self-hosted library**, not a managed service — because the
core pitch *is* data sovereignty (regulated buyers often cannot send data to a 3rd-party
SaaS). Monetization mirrors the pattern already used in `prismresonance` (MIT core +
commercial enterprise features) and `prismrag-patch` (which already ships a `license`
module).

- **OSS core (MIT):** `Memory.digest()` / `Memory.recall()`, bitemporal graph, basic
  content-addressed determinism cache. Drives adoption and trust.
- **Commercial modules (closed, key-gated):** audit/time-travel console,
  consolidation-at-scale, multi-agent Chorus mesh sync, hallucination-verification,
  and the self-hosted batch-invariant "sovereign" determinism tier.
- **Enforcement:** *offline, signed, time-bound license keys* — **no phone-home**
  (a hard requirement for air-gapped/regulated deployments, and a selling point). The
  key gates the *closed* premium wheels, never the open core (a key on open source is
  theater). It doubles as the legal/procurement artifact enterprises need to pay.
- **Pricing:** annual per-deployment/site license tiered by features + scale (do not
  meter usage on self-hosted infra). Second revenue line: support + SLA + indemnification.
- **Not now:** a hosted SaaS tier — it contradicts the sovereignty pitch for the core
  buyer. Revisit only as a low-end quick-start later.

## 8. Open questions
- PrismLang projection confirmed CPU-deterministic? (the read path assumes it)
- Chorus Fabric: standalone package or folded into `prismlib.cluster`?
- Default embedding dim across PrismLang ↔ PrismResonance (384?) — must match.
- Entity-resolution strategy in `sleep()`: embedding threshold + governed rules?
