# PrismCortex — Roadmap & Lessons

The honest record of where this stands, what we learned proving it, and what makes it
genuinely good (not just working). Read alongside [DESIGN.md](DESIGN.md) and
[benchmarks/RESULTS.md](benchmarks/RESULTS.md).

## Where it stands (2026-06-28)
Tech is **real and works** — full-stack run on Azure (2 containers, real Gemini, 0 errors):
determinism, reconsolidation/time-travel, salience-gated cost, memory plateau all PASS.
That proves the *mechanism*, on a *friendly workload we designed*. It does **not** prove
the product is good, robust on messy data, or wanted. Passing your own benchmark is
necessary, not sufficient.

**Verdict:** strong *technology* (~8/10) with one defensible moat (deterministic +
auditable memory); product-readiness early (~4/10); market validation 0/10 (untested).

## Path to GA (enterprise-ready)

**Done:**
- [x] Robust conflict detection (relation normalization) + `sleep()` both-staged fix
- [x] Right-to-be-forgotten (`/forget`) with audit tombstones + cache clear (GDPR)
- [x] Conflict surfacing (`/conflicts`) — never silently serve a contested fact
- [x] Explainability (`/explain`), confidence + freshness, bounded memory (pruning)
- [x] Ed25519 license gate (forge-proof, offline)
- [x] Server auth (API key) + input size limits
- [x] Vectorized retrieval; recall holds **0.98 @ 10k facts** (128-dim)
- [x] Adversarial 4/4; head-to-head vs Mem0; security posture documented (SECURITY.md)

**Still required before calling it GA / signing a regulated customer:**
- [ ] **Subject-level entity resolution under extraction drift** — best-effort today;
      the deeper coref problem. (Mitigated: conflicts are surfaced, not hidden.)
- [ ] **Professional pen-test / security audit** (human — not self-review)
- [ ] **Sustained load test** on Azure with the hardened server (concurrency, mixed R/W,
      error rates under load); real ANN index for 50k+
- [ ] **Real-world messy-data validation** (not synthetic) + multi-tenant isolation
- [ ] **Pin a dated model snapshot**; `pip-audit` + pinned transitive deps; observability
- [ ] **Replace the demo license public key**; rotate keys

## Improvement plan (ranked by leverage)

### #1 — Real entity resolution  ← biggest robustness gap
Exact-label match is brittle. We watched *"production deploy budget"* vs *"deploy budget"*
silently split into two facts. Real chat is full of this ("the budget", "our Q3 spend").
**Fix:** resolve incoming entities against the graph by **embedding similarity** (merge
above a conservative threshold), keep **value** nodes (`$40k` vs `$55k`) distinct, route
the genuinely ambiguous to `sleep()`. This decides whether it survives production data.

### #2 — Build the part that's actually novel (and currently untested)
Every benchmark showed `staged=0`. The **two-speed memory + `sleep()` conflict resolution**
— the differentiated, patent-worthy piece — never fired; reference `sleep()` just merges.
**Fix:** real consolidation — a *silent* conflict (new value, not flagged "correction")
goes to the labile buffer; `sleep()` resolves it (invalidate old, keep newest current,
history retained). #1 and #2 are one investment paying twice: fix the weakest path *and*
build the most novel one.

### #3 — Test where it's hard + head-to-head
- **Scale:** 10k+ facts → measure retrieval **precision/recall**, not just determinism
  (byte-equality passed on an empty graph once — equality ≠ correctness).
- **Adversarial:** contradictions, ambiguous entities, multi-hop questions, deletions.
- **Comparison:** run the same workload through **Mem0 / Zep**. (Needs a Mem0 key or
  self-host.) "Better than the alternative" must become a measurement.

### #4 — Confirm first-render fact-determinism (T3/T4)
Extractive facts + verification pass exist but weren't stressed. Prove the verifier
catches a fabricated number and handles "facts don't contain the answer."

### #5 — Hardening (v0.1 → v1)
Multi-value facts over time, concurrent writes, deletions/forgetting, real test coverage.

## Lessons learned (the gold)
- **Determinism is a cache property, not temp-0.** Shared-API models aren't bitwise
  deterministic (batching + float non-associativity). We route around the model:
  content-address the retrieved subgraph, render once, freeze. Invalidation and
  determinism become the same mechanism.
- **A benchmark you design will pass.** It proves not-vaporware, nothing about demand.
- **"Determinism PASS" can be byte-identical *wrong* answers** — once passed on an empty
  graph. Always check correctness separately from consistency.
- **Memory savings is a *plateau*, not a ratio.** For a short dense conversation the gist
  is *bigger* than raw (~0.4×); savings come from redundancy + accumulation (real chats).
  Don't headline it. Headline determinism + cost.
- **Bugs this exercise surfaced & fixed:** entity attributes dropped on node creation;
  entity-label resolution brittle; `/reset` didn't clear metrics or the durable cache
  (memo carryover → empty re-ingest); Windows `az` CLI crashes on cp1252 (disable pip/HF
  progress bars); ACI ephemeral `/data` is fresh per container (use that, or bump a
  generation counter).
- **The cache is ~120–600× cheaper than the model** (hit ~1–6ms vs ~700ms). That, plus
  97% hit rate, is the real cost story.

## Go-to-market (don't skip for features)
Take the **determinism + audit** demo to 3–5 regulated-enterprise prospects (finance/
health/legal). One "I'd pilot this" = a product. Building more features before that signal
is the trap. Open-core, self-hosted, offline-keyed (see DESIGN.md §7).

## What's needed from outside
- For #3 head-to-head: a **Mem0 API key** (or we self-host Mem0/Zep).
- Everything else (Gemini key, Azure RG/ACR `prismcortexd7a6d0`) is already in place.
