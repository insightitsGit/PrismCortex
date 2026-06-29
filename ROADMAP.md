# PrismCortex — Roadmap & Lessons

The honest record of where this stands, what we learned proving it, and what makes it
genuinely good (not just working). Read alongside [DESIGN.md](DESIGN.md) and
[benchmarks/RESULTS.md](benchmarks/RESULTS.md).

## Where it stands (2026-06-29)
Tech is **real and works** — full-stack run on Azure (2 containers, real Gemini, 0 errors):
determinism, reconsolidation/time-travel, salience-gated cost, memory plateau all PASS.
That proves the *mechanism*, on a *friendly workload we designed*. It does **not** prove
the product is good, robust on messy data, or wanted. Passing your own benchmark is
necessary, not sufficient.

**Verdict:** strong *technology* (~8/10) with one defensible moat (deterministic +
auditable memory); product-readiness early (~4/10); market validation 0/10 (untested).

**Positioning:** sell as **compliance-grade agent memory** (audit + replay + sovereignty),
not as a generic “better RAG / better Mem0.” The wedge is regulated buyers (finance,
health, legal, insurance) who cannot ship append-only chat logs or third-party SaaS memory.

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

---

## Enterprise GA plan (phased)

Phased execution order: **robustness → isolation → scale → compliance packaging →
productized differentiators → GTM**. Do not add net-new engine features until Phase 1–2
are measurably green on messy data.

### Phase 1 — Robustness on messy real-world data (highest leverage)

**Goal:** survive production chat, not just designed benchmarks.

| Item | Status | Deliverable |
|---|---|---|
| Embedding-based entity merge (subjects) | partial | `find_similar_node` + threshold; extend alias table |
| Value nodes stay distinct | done | no fuzzy merge on `kind=value` |
| Relation normalization | done | `_norm_relation` for conflict detection |
| Entity alias / canonical subject IDs | todo | map “the budget” → same subject node |
| Extraction drift hardening | todo | schema-constrained Gemini output + validation |
| Silent conflict → staging → `sleep()` | done | validated in Azure v0.2 |
| Human-in-the-loop for ambiguous merges | todo | API flag + conflict inbox (Phase 5) |
| Messy-data benchmark suite | todo | redacted real transcripts; multi-hop; partial corrections |

**Exit criteria:** adversarial + messy-data suites pass; duplicate-subject rate < 5% on
pilot corpus; conflicts surfaced, never silently served.

### Phase 2 — Multi-tenant isolation & governance

**Goal:** one deployment, many agents/customers, hard boundaries.

| Item | Status | Deliverable |
|---|---|---|
| Per-tenant / per-agent namespace in graph + cache | todo | `tenant_id` on all store ops |
| Cross-tenant retrieval impossible | todo | integration tests proving isolation |
| RBAC on `/digest`, `/recall`, `/forget`, `/audit` | todo | scoped API keys or JWT claims |
| Retention + legal hold policies | todo | policy engine over tombstones + cold storage |
| Data residency hooks | todo | region-pinned PrismLib path / storage backend |
| GDPR erasure | done | `/forget` + cache clear + tombstones |

**Exit criteria:** two tenants on one server cannot read each other’s facts; forget +
audit policies documented for procurement.

### Phase 3 — Scale & SLOs

**Goal:** publish honest capacity numbers enterprise SRE teams can trust.

| Item | Status | Deliverable |
|---|---|---|
| Vectorized retrieval to ~10k facts | done | 0.98 hit@8 @ 128-dim |
| Real ANN index (PrismRAG) for 50k+ | todo | swap reference linear scan |
| Sustained mixed R/W load test | todo | Azure: concurrency, p99, error rate |
| Write-path backpressure | todo | queue or 429 when digest backlog high |
| Capacity guide | todo | “X facts, Y QPS, Z vCPU” doc in RESULTS.md |
| Horizontal read scaling story | todo | read replicas or cache tier (design doc) |

**Exit criteria:** p99 recall < 50 ms @ 50k facts (cached); digest p99 documented;
zero data loss under concurrent writes test.

### Phase 4 — Security & compliance packaging

**Goal:** pass procurement, not just engineering review.

| Item | Status | Deliverable |
|---|---|---|
| API key auth + input limits | done | server.py |
| Ed25519 offline license | done | licensing.py |
| `pip-audit` clean | done | benchmarks/results/pip_audit.txt |
| Replace demo license public key | todo | operator keypair + runbook |
| Model `@epoch` pin | done | PRISMCORTEX_MODEL + cache invalidation |
| SBOM + pinned transitive deps per release | todo | lockfile + CI artifact |
| Rate limiting | todo | proxy doc + optional in-app middleware |
| Prompt-injection hardening | todo | structured extraction; system/user separation |
| Third-party pen-test | todo | external vendor report |
| SOC 2 / ISO roadmap | todo | one-pager for sales (even “in progress”) |

**Exit criteria:** pen-test findings remediated or accepted with compensating controls;
SECURITY.md matches shipped behavior.

### Phase 5 — Operational observability

**Goal:** regulated ops can run and debug this without reading source.

| Item | Status | Deliverable |
|---|---|---|
| `/metrics` + structured JSON logs | done | server.py |
| OpenTelemetry traces | todo | digest → extract → commit → recall spans |
| Dashboards | todo | cache hit rate, staged backlog, conflict count, version churn |
| Alerts | todo | sleep backlog growth, extraction failure rate |
| Model epoch governance UI/workflow | todo | bump epoch → invalidate cache (documented ops runbook) |

**Exit criteria:** on-call can diagnose “wrong answer” from traces + `/explain` in < 15 min.

### Phase 6 — Productize differentiators (commercial tier)

**Goal:** the demo *is* the product for enterprise buyers.

| Item | Status | Deliverable |
|---|---|---|
| Explain API | done | `/explain` — evidence trail |
| Conflict API | done | `/conflicts` |
| Time-travel / audit API | partial | bitemporal graph; needs `/audit` UX |
| Audit console (time-travel UI) | todo | “what did we believe on date X?” |
| Conflict inbox UI | todo | human resolve → commit |
| Replay certificate export | todo | hash(subgraph@v) + frozen render proof |

**Exit criteria:** 15-minute demo: ingest → correct → time-travel → explain → replay.

### Phase 7 — Competitive proof & GTM

**Goal:** one regulated pilot before more features.

| Item | Status | Deliverable |
|---|---|---|
| Head-to-head vs Mem0 | partial | benchmarks/vs_mem0.py |
| Head-to-head vs Zep | todo | same workload script |
| Correctness metrics separate from determinism | todo | always report both in RESULTS.md |
| 3–5 regulated prospect demos | todo | finance / health / legal |
| Annual site license + SLA package | todo | DESIGN.md §7 commercial wrapper |

**Exit criteria:** at least one “I’d pilot this” from a regulated prospect; published
comparison showing audit + replay advantage (not just latency).

### Explicitly deferred (do not build yet)

- Hosted SaaS tier (contradicts sovereignty pitch for core buyer)
- First-render token determinism without sovereign tier (T5) as default claim
- Chasing generic dev-tool market on “remember stuff” alone

---

## Improvement plan (ranked by leverage)

### #1 — Real entity resolution  ← biggest robustness gap
Exact-label match is brittle. We watched *"production deploy budget"* vs *"deploy budget"*
silently split into two facts. Real chat is full of this ("the budget", "our Q3 spend").
**Fix:** resolve incoming entities against the graph by **embedding similarity** (merge
above a conservative threshold), keep **value** nodes (`$40k` vs `$55k`) distinct, route
the genuinely ambiguous to `sleep()`. **v0.2 landed embedding merge + unit tests; still
need alias/canonical IDs and messy-data validation.**

### #2 — Two-speed memory + `sleep()` consolidation
The differentiated, patent-worthy piece. **v0.2 validated end-to-end on Azure** (silent
conflict → labile buffer → `sleep()` → accommodate, history retained). Keep stress-testing
under real Gemini extraction drift.

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
