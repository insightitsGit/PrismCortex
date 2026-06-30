# PrismCortex — GTM, Landing Page & Trial Spec

> **Audience:** AI agents and humans building the **insightits.com** landing page, Stripe/checkout,
> trial provisioning, and sales collateral.  
> **Framework:** [Alex Hormozi playbook](../alex-hormozi.md) — Value Equation, Grand Slam Offer.  
> **Product:** PrismCortex — deterministic, auditable, self-consolidating memory for AI agents.  
> **Company site:** https://www.insightits.com (production Azure; Flask/React stack per site README)  
> **Maintainer:** Insight IT Solutions LLC · info@insightits.com · +1 (973) 692-6919

---

## 0. Executive recommendation — 30-day trial + landing page

**Yes — do this.** A **hosted 30-day validation trial** on your **production Azure** is the right
move for a first release with no customer logos. It fixes the weakest Hormozi lever
(**Perceived Likelihood**) without contradicting the sovereignty pitch:

| Mode | Purpose | Where |
|------|---------|--------|
| **30-day Validation Trial** | Prospect tries replay, audit console, `/explain` on **Insight ITS Azure sandbox** | Hosted demo URL + time-limited license key |
| **Production** | Customer runs memory in **their** VPC / region | Self-hosted Docker or library + **annual license key** |

**Critical messaging:** Trial is *evaluation infrastructure* — not production PHI/PII. Production
is always self-hosted. Same pattern as PrismRAG SaaS free tier vs enterprise self-host.

**Do NOT:** Ship production customer data to trial sandbox without BAA/DPA.  
**DO:** Auto-expire trial keys at 30 days; cap usage (requests/day, graph size).

---

## 1. What this product is (plain language)

**PrismCortex is compliance-grade agent memory** — not another vector database or chat log.

1. **Digest** — each turn → knowledge graph (gist, not raw logs).  
2. **Consolidate** — uncertain facts stage; `sleep()` resolves conflicts.  
3. **Recall** — LLM is *renderer* only; answers frozen, byte-replayable, evidence-linked.

**One-line pitch:**

> Ship AI agents that regulators can audit — byte-identical replay, bitemporal history, and corrections that never silently erase the past.

**What it is NOT:**

- Generic "better RAG" or "cheaper Mem0"
- Production hosted SaaS for regulated data (trial sandbox only)
- "Temperature 0 = identical LLM output"

**Two integration surfaces (both real today):**

```python
# A) Python library (in-process)
from prismcortex import reference_memory
mem = reference_memory()
mem.digest("My deploy budget is $40,000.")
mem.recall("What's my deploy budget?").answer
```

```bash
# B) HTTP service (same engine — what Azure benchmark uses)
curl -X POST https://<host>:8080/digest -H "X-API-Key: ..." -d '{"text":"..."}'
curl -X POST https://<host>:8080/recall -H "X-API-Key: ..." -d '{"query":"..."}'
# OpenAPI when server running: /docs
```

---

## 2. Market avatar

| Dimension | Choice |
|-----------|--------|
| **Primary** | VP Eng / Head of AI Platform / CCO at **regulated B2B** (finance, insurance, health, legal, gov) |
| **Pain** | Legal blocks append-only logs, black-box retrieval, third-party memory SaaS |
| **Budget** | CISO + GC + VP Eng jointly |
| **Wedge** | Compliance + audit + sovereignty — not "remember preferences" |

---

## 3. Dream outcome

Pass compliance review and ship production agents with memory auditors can **replay, time-travel,
and explain** — self-hosted in the customer's region within 30–90 days.

---

## 4. Value equation (1–10)

| Variable | Score | Fix |
|----------|-------|-----|
| Dream Outcome | 9 | — |
| Perceived Likelihood | **5→7 with trial** | 30-day hosted validation + benchmarks on page |
| Time Delay | 7 | Trial instant; prod deploy 3–7 days |
| Effort | 6 | Library or Docker; trial removes install friction |

---

## 5. Offer ladder & pricing (publish on landing page)

### Public pricing table

| Plan | Price | Duration | Best for | License |
|------|-------|----------|----------|---------|
| **OSS Core** | **Free** | Forever | Developers, PoC in dev | MIT — no key |
| **Validation Trial** | **Free** | **30 days** | Compliance/engineering evaluation | Time-limited Ed25519 key + sandbox API key |
| **Compliance Pilot** | **$15,000** one-time | 14–30 days | Staging on *their* infra | Pilot key; **100% credit** to Year 1 if convert in 90 days |
| **Pro** | **$32,000 / year** | Annual prepay | Single prod deployment, ≤5 tenants | `tier: pro` offline key |
| **Enterprise** | **from $75,000 / year** | Annual prepay | Regulated production, 24×7 | `tier: enterprise` offline key |
| **Founding Enterprise** | **$45,000 / year** | Locked 2 years | **First 5** design partners only | Same + founding badge in contract |

**Add-ons:** Professional services $200–250/hr · extra deployment +50% license · 2-year prepay −12%.

### What each tier unlocks (commercial modules = license-gated)

| Feature | OSS | Trial | Pro | Enterprise |
|---------|-----|-------|-----|------------|
| `digest` / `recall` / bitemporal graph | ✅ | ✅ | ✅ | ✅ |
| Audit console `/console` | ❌ | ✅ | ✅ | ✅ |
| `/recall_at` time-travel | ❌ | ✅ | ✅ | ✅ |
| `/replay_certificate` | ❌ | ✅ | ✅ | ✅ |
| Multi-tenant + RBAC | ❌ | 1 tenant | ≤5 tenants | Unlimited |
| Legal hold + policy | ❌ | ❌ | ✅ | ✅ |
| 24×7 P1 support | ❌ | ❌ | Business hours | ✅ |
| Custom SLA + indemnification | ❌ | ❌ | ❌ | Negotiated |

### Guarantee (Pilot only)

> **Replay Guarantee:** Byte-identical replay certificates on ≥3 agreed audit queries within 14 days on staging, or full pilot fee refunded.

### ROI anchor (pricing calculator on page)

```
6-month launch delay .............. ~$400,000 opportunity cost
Excess LLM re-extraction .......... ~$8,000/mo (~$96k/yr)
Founding Enterprise ............... $45,000/yr
Payback if launch unblocks ........ < 2 months
```

---

## 6. 30-day Validation Trial — product spec

### Goal

Let a qualified lead **experience** replay determinism and audit trail in **< 10 minutes**
without installing Docker. Converts Likelihood; filters serious buyers.

### User flow (landing page)

```
1. Click "Start 30-Day Validation" → short form (work email, company, role, use case checkbox)
2. Email verification (optional but recommended — blocks abuse)
3. Provision:
   - PRISMCORTEX_LICENSE_KEY (30-day expiry, tier=trial, features=[console,recall_at,replay])
   - PRISMCORTEX_API_KEY (scoped: read+write, rate-limited)
   - Trial URL: https://prismcortex-demo.insightits.com (or Azure FQDN — see infra)
4. Welcome email: curl examples, link to /console, link to benchmark PDF
5. Day 25 email: "Upgrade to Pilot / Enterprise" + key expiry warning
6. Day 30: key expires; sandbox data deleted (state retention policy in ToS)
```

### Trial limits (enforce server-side)

| Limit | Value |
|-------|-------|
| Duration | 30 calendar days |
| Requests | 1,000 digest + 5,000 recall / day |
| Graph size | 5,000 facts max |
| Tenants | 1 (`trial-{uuid}`) |
| Data | **No production PHI/PII** — evaluation only (checkbox + ToS) |
| Gemini | Shared trial key (Insight ITS) — customer BYOK on prod |

### Trial infra (use existing Azure)

Reuse **`prismcortex-rg`** pattern from this repo:

- ACR: `prismcortexd7a6d0.azurecr.io/prismcortex:bench`
- Server: 4 vCPU / 8 GB ACI or App Service container
- **Always-on for trial** (budget ~$50–150/mo depending on shape) OR scale-to-zero with cold start note
- Auth: per-trial API key in `PRISMCORTEX_API_KEYS` JSON or DB-backed key store
- License: `issue_key()` from `prismcortex/licensing.py` — **replace demo pubkey first** ([KEY_ROTATION.md](docs/KEY_ROTATION.md))

### Trial vs production (copy for FAQ)

> **Trial** runs on Insight ITS Azure for evaluation. **Production** runs in your VPC with an offline license key — your data never leaves your environment.

---

## 7. License key fulfillment (all paid plans)

**Mechanism already built:** `prismcortex/licensing.py` — Ed25519, offline, no phone-home.

```python
# Run on secure issuer machine (PRIVATE key never in repo)
from prismcortex.licensing import issue_key
key = issue_key(
    private_key_hex="...",
    tier="enterprise",
    expiry_iso="2027-06-30T00:00:00+00:00",
    customer="Acme Corp",
    features=["console", "recall_at", "multi_tenant", "legal_hold"],
)
# Deliver key in email + customer portal; customer sets PRISMCORTEX_LICENSE_KEY
```

**Website agent:** implement admin script or Stripe webhook → call issuer → email key.  
**v1 manual is OK:** form → sales → issue key within 24h.

---

## 8. Proof bar — full benchmark pack (paste on landing page)

**Badge line:** `Azure-validated · real Gemini · v0.2.1 · ACR build ca9 · Jun 2026`

### Azure E2E core (production path)

| Metric | Result |
|--------|--------|
| Cross-container determinism | **24/24** byte-identical replays |
| Reconsolidation | **$40k → $55k**; superseded fact retained |
| Conflict resolution | **staged → `sleep()`**; history kept |
| Memory plateau (675 chatter turns) | edges **30 → 30** |
| Gist vs raw log | **5.20×** smaller |
| Cache hit rate | **99.57%** (30 Gemini / 2,563 recalls) |
| Cached replay latency | **~6 ms** vs **~724 ms** first render |
| Throughput (cached, c=20) | **141 req/s**, p95 **159 ms** |
| Mixed workload (c=20) | **0 errors** / 500 requests |
| Server errors (core path) | **0** |

### Scale / ANN (no LLM — `benchmarks/results/scale_ann.json`)

| Facts | Nodes | hit@8 | retrieve p95 |
|-------|-------|-------|--------------|
| 10,000 | 20,000 | **91.5%** | 10 ms |
| **50,000** | **100,000** | **85.0%** | **74 ms** |

### Honest limits (FAQ — builds trust)

| Do NOT claim | Say instead |
|--------------|-------------|
| 50 concurrent clients, zero errors | **~20 concurrent clients / 4 vCPU node** (validated) |
| SOC 2 certified | **SOC 2-aligned controls; Type I in progress** |
| Hosted production for regulated data | **Trial sandbox only; production self-hosted** |
| Customer logos | **Azure-validated benchmarks** (first release) |

### Proof assets to link or embed

| Asset | Path / URL |
|-------|------------|
| Full benchmark write-up | `benchmarks/RESULTS.md` (host PDF export on site) |
| Machine-readable scorecard | `benchmarks/results/results.json` |
| Scale ANN JSON | `benchmarks/results/scale_ann.json` |
| SLA / reference SLO | `docs/SLA.md` |
| SOC 2 readiness | `docs/SOC2_ROADMAP.md` |
| Security | `SECURITY.md` + pen-test status on website |
| GitHub | https://github.com/insightitsGit/PrismCortex |

---

## 9. Landing page spec — insightits.com

### Recommended URL

Follow existing product pattern:

- **Primary:** `https://www.insightits.com/products/prismcortex.html`
- **Trial signup:** `https://www.insightits.com/products/prismcortex/trial` (or `/trial/prismcortex`)
- **Add to:** `https://www.insightits.com/ai-info.txt` and sitemap.xml
- **Section:** "AI Infrastructure Platform" alongside PrismRAG, PrismLang, CHORUS, PrismResonance

### Page sections (top → bottom)

1. **Hero** — "Agent memory your auditors can actually trust."  
   CTAs: **Start 30-Day Validation** (primary) · **View benchmark proof** (secondary)

2. **Proof bar** — 24/24 · 99.6% cache · 0 errors · 5.2× · 6 ms replay

3. **Problem** — compliance blocked / drift / SaaS rejected

4. **How it works** — Digest → Consolidate → Recall (diagram from README)

5. **Library or API** — two tabs: Python embed vs Docker/HTTP service

6. **Differentiation table** — vs append-only RAG / vs vector stores (README table)

7. **Benchmark deep-dive** — collapsible numbers from §8

8. **Pricing** — table from §5 + Founding Enterprise callout

9. **Trial block** — what's included, limits, "evaluation only" disclaimer

10. **Security & compliance** — self-hosted prod, SOC2 roadmap, pen-test status, GDPR `/forget`

11. **FAQ** — from §8 honest limits

12. **Final CTA** — Start trial · Book Agent Memory Audit · Contact sales

### CTAs (named)

| Button | Action |
|--------|--------|
| Start 30-Day Validation | Trial signup form → provision keys |
| Book Agent Memory Audit | Calendly / info@insightits.com |
| Start Compliance Pilot | Contact sales $15k |
| Install OSS Core | `pip install prismcortex` + GitHub |
| Talk to Enterprise | info@insightits.com |

### Design

- Match PrismRAG product pages on insightits.com
- Reuse audit console palette: `#0f1419` bg, `#5b9bd5` accent (see `prismcortex/static/index.html`)
- Tone: compliance-grade infrastructure, not playful chatbot SaaS

### SEO

- **Title:** PrismCortex — Compliance-Grade Agent Memory | Insight IT Solutions  
- **Description:** Self-hosted AI agent memory with byte-identical replay and bitemporal audit. 30-day validation trial. Azure-validated benchmarks.  
- **Keywords:** agent memory, auditable AI, bitemporal memory, self-hosted LLM memory, regulated AI

---

## 10. Agent handoff — how to implement on insightits.com

> **For the website implementation agent.** PrismCortex repo is separate from the marketing site repo.
> Site stack (per insightits.com): Python/Flask backend, React/Vite frontend, AWS/Azure hosting.

### Phase A — Static landing (Week 1)

1. Create `products/prismcortex.html` from §9 content; pull copy from §10–12 Copy Bank below.
2. Add product card to homepage "AI Infrastructure Platform" grid (match `prismrag.html` layout).
3. Update `sitemap.xml` and `ai-info.txt`.
4. Host downloadable **Benchmark Summary PDF** (export from `benchmarks/RESULTS.md`).
5. Embed proof numbers from §8 — do not invent stats.

### Phase B — Trial signup (Week 2)

1. **Form fields:** work email, name, company, role (dropdown), use case (regulated checkbox), agree ToS + no-PHI.
2. **Backend endpoint** (Flask on insightits Azure):
   - Validate email domain (block gmail.com for trial optional)
   - Create trial record in DB (email, company, `trial_id`, `expires_at`, `api_key_hash`)
   - Call license issuer (secure sidecar or manual queue v1)
   - Send welcome email with: trial URL, API key, license key, curl snippet
3. **Rate limit:** max 3 trials per company domain per quarter.
4. **Manual fallback v1:** form → email to info@insightits.com → ops runs script within 24h.

### Phase C — Trial sandbox (Week 2–3)

1. Deploy PrismCortex server image to Azure (reuse `deploy/run_only.sh` patterns; **keep container running** for trial).
2. Set env: `PRISMCORTEX_API_KEYS='{"trial-xxx": {"tenant": "trial-xxx", "roles": ["read","write","admin"]}}'`
3. Public URL behind HTTPS (Azure Front Door or nginx): `prismcortex-demo.insightits.com`
4. Wire `/console` for trial users (pass API key in UI or query param — document in welcome email).
5. Cron: delete expired tenant data; revoke keys at day 30.

### Phase D — Paid checkout (Week 3–4, optional)

1. Stripe Checkout for Pilot ($15k) and Pro/Enterprise (invoice or Stripe).
2. Webhook → generate license key → email + optional customer portal page.
3. Enterprise: always human-in-loop (contact sales) — no self-serve $75k checkout.

### Files in PrismCortex repo the site agent may need

| File | Purpose |
|------|---------|
| `prismcortex/static/index.html` | Audit console UI — link as "see the console" |
| `prismcortex/licensing.py` | Key issue/verify |
| `docs/SLA.md`, `docs/SUPPORT.md` | Legal/support links |
| `benchmarks/RESULTS.md` | Proof content |
| `Dockerfile` + `docker/entrypoint.sh` | Container deploy |
| `deploy/run_only.sh` | Azure deploy reference |

### API reference for trial page (developer tab)

```
GET  /health
POST /digest        {"text": "...", "source_id": "optional"}
POST /recall        {"query": "..."}
POST /explain       {"query": "..."}
GET  /replay_certificate?query=...
GET  /console       (static audit UI)
```

Auth header: `X-API-Key: <trial-key>`

---

## 11. Pain → Proof → Plan (messaging)

**Pain:** Legal killed the launch. Append-only logs can't answer "what did we know on March 3rd?"

**Proof:** §8 benchmark table + link to validation trial.

**Plan:**

1. **Start 30-day validation** — replay + audit console on Insight ITS Azure.  
2. **Compliance pilot** — deploy on your staging; replay certificates on your queries.  
3. **Production** — annual license, your infra, your region, SLA-backed support.

---

## 12. Copy bank

### Headlines

- Agent memory your auditors can actually trust.
- Ship AI agents without failing compliance.
- When legal asks "what did the agent know?" — have an answer.

### Subheads

- Self-hosted production. Hosted 30-day validation. Replay-deterministic. Bitemporal audit.

### Elevator pitch (30 sec)

"Regulated companies can't ship AI agents because memory is either an append-only chat log or a third-party SaaS compliance won't approve. PrismCortex is self-hosted agent memory that digests conversations into an auditable graph, consolidates conflicts in the background, and replays answers byte-identically with evidence trails. We validated on Azure with real Gemini — 24/24 replays identical, 99.6% cache hit, zero server errors. Start a free 30-day validation on our sandbox; run production in your VPC with an offline license key."

### SLA one-liners (from docs/SLA.md)

> Compliance-grade agent memory — byte-identical replay, bitemporal audit, corrections without wiping history.

> ~6 ms cache replay vs ~700 ms first render — the cache is the determinism and the cost story.

> ~20 concurrent memory clients per 4 vCPU node (validated mixed workload).

---

## 13. Security & compliance copy (website)

| Topic | Landing page text |
|-------|-------------------|
| Pen-test | "Independent penetration test [scheduled Q3 2026 / report available under NDA post-pilot]" — **update when live on insightits.com** |
| SOC 2 | "SOC 2 Type I readiness documented; formal attestation in progress" |
| GDPR | `/forget` with audit tombstones; legal hold API |
| Trial data | "Evaluation sandbox only — do not submit production PHI/PII" |
| Production | "Self-hosted; offline Ed25519 license; no phone-home" |

---

## 14. Channels & 30-day GTM sprint

| Week | Action |
|------|--------|
| 1 | Ship `prismcortex.html` + proof bar + pricing |
| 2 | Trial signup live + sandbox URL |
| 3 | 5-min replay demo video ($40k→$55k, `/console`) |
| 4 | 10 outbound "Agent Memory Audit" messages; cap founding slots at 5 |

---

## 15. Product facts (accuracy checklist)

| Fact | Value |
|------|-------|
| Version | v0.2.0 / v0.2.1 benchmarks |
| Library | `pip install prismcortex` · `reference_memory()` |
| HTTP service | FastAPI on `:8080` · `/docs` OpenAPI |
| License | MIT core + Ed25519 commercial key |
| Trial | 30 days hosted sandbox + time-limited key |
| Production | Self-hosted Docker/library + annual key |
| GitHub | insightitsGit/PrismCortex |
| Contact | info@insightits.com · +1 (973) 692-6919 |
| Related products | PrismRAG, PrismLang, PrismResonance, CHORUS (insightits.com/products/) |

---

*Single source of truth for landing page agents. Product: [README.md](README.md), [ROADMAP.md](ROADMAP.md), [benchmarks/RESULTS.md](benchmarks/RESULTS.md), [docs/SLA.md](docs/SLA.md). Framework: [alex-hormozi.md](../alex-hormozi.md).*
