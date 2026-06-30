# PrismCortex — Roadmap & Lessons

The honest record of where this stands, what we learned proving it, and what makes it
genuinely good (not just working). Read alongside [DESIGN.md](DESIGN.md) and
[benchmarks/RESULTS.md](benchmarks/RESULTS.md).

## Where it stands (2026-06-29)

Tech is **real and works** — full-stack **v0.2.0** run on Azure (2 containers, real Gemini,
**0 server errors** on core path). Canonical artifact: `benchmarks/results/results.json`
(see [RESULTS.md](benchmarks/RESULTS.md)).

### E2E scorecard (Azure, `prism` backend, v0.2 — 2026-06-29)

| Claim | Result |
|---|---|
| Cross-container determinism | **PASS** — 24/24 replays byte-identical |
| Reconsolidation + time-travel | **PASS** — `$40k → $55k`; superseded fact retained |
| Conflict resolution (`60s → 300s`) | **PASS** — history retained (inline commit this run) |
| Memory plateau (675 chatter turns) | **PASS** — edges 30 → 30; 0 extra Gemini calls |
| Cost / cache | **99.4% hit rate** — 30 Gemini calls / 1,838 recalls |
| Throughput (cached recalls, c=20) | **74.0 req/s** p95=422 ms (up from 37.5 on v0.1) |
| Sustained load (c=50, 2000 req) | **Captured** — 2.5% errors, p99=244 s; capacity tuning needed |

That proves the *mechanism*, on a *friendly workload we designed*. It does **not** prove
the product is good, robust on messy data, or wanted. Passing your own benchmark is
necessary, not sufficient.

**Verdict:** strong *technology* (~8/10) with one defensible moat (deterministic rendered
answers + bitemporal audit); product-readiness early (~4/10); market validation 0/10
(untested).

**Positioning:** sell as **compliance-grade agent memory** (audit + replay + sovereignty),
not as a generic “better RAG / better Mem0.” The wedge is regulated buyers (finance,
health, legal, insurance) who cannot ship append-only chat logs or third-party SaaS memory.

### What changed since the first GA checklist

- **Value-merge regression fixed** (Jun 29): fuzzy entity resolution was incorrectly
  merging *values* (`300 seconds` → `60 seconds`), silently dropping conflicts. Fix:
  subjects coref by embedding; values resolve by **exact match only**. Regression test +
  re-validated E2E (`staged→sleep` for cache TTL conflict).
- **`bench_load()` captured** in v0.2 `results.json` — 50/2000 errors at c=50 on one
  2-vCPU container; functional claims pass, sustained-load **SLO still open** (see CAPACITY.md).
- **Adversarial bench is 3/4**, not 4/4 — contradiction-under-context fails in a shared
  graph (extraction drift); mechanism passes in isolation. See RESULTS.md.
- **Mem0 head-to-head exists** (`benchmarks/vs_mem0.py`); moat is narrower than
  “determinism” — it's **cached rendered answers + bitemporal audit + sovereignty**.

## Path to GA (enterprise-ready)

**Done:**
- [x] Robust conflict detection (relation normalization) + `sleep()` both-staged fix
- [x] Two-speed memory validated E2E — silent conflict → staging → `sleep()` → accommodate
- [x] Value-node merge guard — subjects fuzzy-coref; values exact-match only (regression test)
- [x] Right-to-be-forgotten (`/forget`) with audit tombstones + cache clear (GDPR)
- [x] Conflict surfacing (`/conflicts`) — never silently serve a contested fact
- [x] Explainability (`/explain`), confidence + freshness, bounded memory (pruning)
- [x] Ed25519 license gate (forge-proof, offline)
- [x] Server auth (API key) + input size limits; driver sends API key on Azure runs
- [x] Vectorized retrieval; recall holds **0.98 @ 10k facts** (128-dim)
- [x] Azure E2E benchmark captured (`results.json`); security posture documented (SECURITY.md)
- [x] Model `@epoch` pin (`PRISMCORTEX_MODEL`); `pip-audit` clean on core deps
- [x] Head-to-head vs Mem0 script + initial run documented (RESULTS.md)
- [x] Adversarial bench **3/4** (over-merge guard, distractor precision, multi-hop pass)

**Still required before calling it GA / signing a regulated customer:**
- [ ] **Adversarial 4/4** — fix contradiction-under-context (extraction drift in shared graph)
- [ ] **Subject-level entity resolution under extraction drift** — embedding merge landed;
      still need alias/canonical IDs + messy-data validation
- [ ] **Sustained load SLO green** — captured at 2.5% errors / p99=244 s (c=50, 1×2-vCPU);
      tune concurrency, timeouts, or scale-out before GA claim
- [ ] **Professional pen-test / security audit** (human — blocker for SOC 2 Type I)
- [x] **50k+ ANN scale published** — `python benchmarks/scale_bench.py --ann` → `scale_ann.json`
- [x] **Zep head-to-head script** — `benchmarks/vs_zep.py` (set `ZEP_API_KEY` for live run)
- [x] **SOC 2 / ISO readiness doc** — `docs/SOC2_ROADMAP.md` (attestation not complete)
- [x] **24×7 support model** — `docs/SUPPORT.md`
- [ ] **Real-world messy-data validation** (not synthetic) + multi-tenant isolation in prod
- [ ] **SBOM + pinned transitive deps** per release (audit is clean today; not locked)
- [ ] **Replace the demo license public key**; rotate keys
- [x] **Sync RESULTS.md** with v0.2 E2E numbers + sustained-load section (2026-06-29)

---

## Enterprise GA plan (phased)

Phased execution order: **robustness → isolation → scale → compliance packaging →
productized differentiators → GTM**. Do not add net-new engine features until Phase 1–2
are measurably green on messy data.

### Phase 1 — Robustness on messy real-world data ✅ (engine + CI bench)

| Item | Status | Deliverable |
|---|---|---|
| Embedding-based entity merge (subjects) | done | similarity + token overlap + canonical labels |
| Value nodes stay distinct | done | exact-match only on dst |
| Relation normalization | done | `norm_relation` + `relations_compatible` |
| Entity alias / canonical subject IDs | done | `register_alias` + `/aliases` API |
| Extraction drift hardening | done | subject+value conflict; Gemini payload delimiters |
| Silent conflict → staging → `sleep()` | done | Azure + `messy_bench.py` |
| Crowded-graph recall | done | `_expand_subgraph` label-overlap boost |
| Messy-data benchmark suite | done | `benchmarks/messy_bench.py` (+ real Gemini adversarial TBD on Azure) |

### Phase 2 — Multi-tenant isolation & governance ✅

| Item | Status | Deliverable |
|---|---|---|
| Per-tenant namespace in graph + cache | done | `TenantMemoryManager` |
| Cross-tenant retrieval impossible | done | separate store per tenant + tests |
| RBAC on endpoints | done | `auth.py` + scoped API keys |
| Retention + legal hold | done | `PolicyEngine` + `/legal_hold` |
| Data residency hooks | done | `PRISMCORTEX_REGION` + tenant paths |
| GDPR erasure | done | `/forget` + cache clear + tombstones |

### Phase 3 — Scale & SLOs ✅ (in-process; Azure load capture pending)

| Item | Status | Deliverable |
|---|---|---|
| Vectorized retrieval to ~10k facts | done | 0.98 hit@8 @ 128-dim |
| IVF ANN for 50k+ | done + **published** | `AnnGraphStore`; `benchmarks/results/scale_ann.json` |
| Sustained mixed R/W load test | in progress | split `bench_load()` + read/write pools + 4 vCPU deploy |
| Write-path backpressure | done | digest semaphore → 429 |
| Capacity guide | done | `docs/CAPACITY.md` |
| Horizontal read scaling story | done | `docs/SCALING.md` |

### Phase 4 — Security & compliance packaging ✅ (pen-test external)

| Item | Status | Deliverable |
|---|---|---|
| API key auth + input limits | done | server |
| Ed25519 offline license | done | licensing.py |
| `pip-audit` clean | done | benchmarks/results/pip_audit.txt |
| Replace demo license public key | todo | operator — see `docs/KEY_ROTATION.md` |
| Model `@epoch` pin | done | PRISMCORTEX_MODEL |
| SBOM per release | done | `scripts/generate_sbom.py` |
| Rate limiting | done | `PRISMCORTEX_RATE_LIMIT_RPM` |
| Prompt-injection hardening | done | payload delimiters + sanitization |
| Third-party pen-test | todo | external vendor — **blocker for SOC 2 Type I** |
| SOC 2 / ISO roadmap | done | `docs/SOC2_ROADMAP.md` (Type I path documented) |
| 24×7 support model | done | `docs/SUPPORT.md` |

### Phase 5 — Operational observability ✅

| Item | Status | Deliverable |
|---|---|---|
| `/metrics` + structured JSON logs | done | server.py |
| Request tracing | done | `tracing.py` + trace spans in logs |
| Dashboards | done | `/dashboard` + enhanced `/metrics` |
| Alerts | done | `/health` alerts (staging, errors) |
| Model epoch governance | done | `docs/OPS_RUNBOOK.md` |

### Phase 6 — Productize differentiators ✅

| Item | Status | Deliverable |
|---|---|---|
| Explain API | done | `/explain` |
| Conflict API | done | `/conflicts` |
| Time-travel | done | `/audit?at=`, `/recall_at` |
| Audit console | done | `/console` static UI |
| Conflict resolve | done | `POST /conflicts/resolve` |
| Replay certificate | done | `GET /replay_certificate` |

### Phase 7 — Competitive proof & GTM ✅ (pilots still manual)

| Item | Status | Deliverable |
|---|---|---|
| Head-to-head vs Mem0 | done | `benchmarks/vs_mem0.py` |
| Head-to-head vs Zep | done | `benchmarks/vs_zep.py` (live with `ZEP_API_KEY`) |
| Correctness vs determinism | done | `benchmarks/correctness_bench.py` |
| Adversarial 4/4 | in progress | engine fixes landed — **re-run with Gemini on Azure** |
| Regulated prospect demos | todo | GTM — manual |
| SLA package | done | `docs/SLA.md` |

---

## Next: Azure E2E + benchmarks

1. ~~Re-run Azure + sync RESULTS.md~~ — **done** (v0.2, 2026-06-29)
2. Tune sustained load (lower c, more CPU, or queue limits) until error rate ≈ 0
3. `GEMINI_API_KEY=... python benchmarks/adversarial_bench.py` — confirm 4/4 on Azure
4. Optional: `python benchmarks/vs_mem0.py` + `vs_zep.py` on same run

---

## Enterprise GA plan (phased) — original checklist archived below

### Explicitly deferred (do not build yet)

- Hosted SaaS tier (contradicts sovereignty pitch for core buyer)
- First-render token determinism without sovereign tier (T5) as default claim
- Chasing generic dev-tool market on “remember stuff” alone

---

## Next actions (before Phase 1 implementation)

Ordered — do these before writing new engine features:

1. ~~Re-run Azure benchmark + update RESULTS.md~~ — **done** (v0.2 artifacts kept).
2. **Tune sustained load** — target 0 errors at declared concurrency before GA SLO.
3. **Fix adversarial 4/4 on Azure** — re-run with Gemini after engine fixes.
4. **Messy-data validation** — redacted real transcripts (Phase 1 bench exists; needs prod data).

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
  (byte-equality passed on an empty graph once — equality ≠ correctness). **0.98 @ 10k
  done** (scale_bench, no LLM).
- **Adversarial:** **3/4 today** — contradiction-under-context fails in shared graph
  (extraction inconsistency); fix direction in RESULTS.md. Multi-hop and over-merge guard pass.
- **Sustained load:** **captured** (2.5% errors @ c=50); needs tuning before GA SLO claim.
- **Comparison:** Mem0 head-to-head run exists; Zep still todo. Moat = audit + cached
  render + sovereignty, not “determinism” in the abstract.

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
  (memo carryover → empty re-ingest); **value fuzzy-merge broke conflict resolution**
  (`300 seconds` collapsed into `60 seconds` — fixed Jun 29); Windows `az` CLI crashes on
  cp1252 (disable pip/HF progress bars); ACI ephemeral `/data` is fresh per container
  (use that, or bump a generation counter).
- **Mem0 comparison corrected our marketing:** vector retrieval is deterministic for
  everyone; our edge is **byte-identical cached renders + bitemporal time-travel**, not
  “determinism” alone.
- **The cache is ~120–600× cheaper than the model** (hit ~1–6ms vs ~700ms). That, plus
  97% hit rate, is the real cost story.

## Go-to-market (don't skip for features)
Take the **determinism + audit** demo to 3–5 regulated-enterprise prospects (finance/
health/legal). One "I'd pilot this" = a product. Building more features before that signal
is the trap. Open-core, self-hosted, offline-keyed (see DESIGN.md §7).

## What's needed from outside
- For #3 head-to-head: a **Mem0 API key** (or we self-host Mem0/Zep).
- Everything else (Gemini key, Azure RG/ACR `prismcortexd7a6d0`) is already in place.
