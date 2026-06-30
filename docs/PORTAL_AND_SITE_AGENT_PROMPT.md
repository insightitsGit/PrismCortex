# Agent prompt — PrismCortex GTM, portal & landing page

> **Copy everything below the line into a new agent session** working on the **Insight ITS production app** (insightits.com + customer portal). Fix as much as you can without inventing claims or secrets.

---

## Your mission

Implement PrismCortex go-to-market in the **main Insight ITS production app** and **marketing site** so buyers can:

1. **Learn** — product landing page with honest benchmarks and competitive positioning  
2. **Try** — 30-day validation trial (hosted sandbox, evaluation only)  
3. **Buy** — Stripe checkout / invoices for Pilot and Pro tiers  
4. **Manage** — logged-in portal: licenses, billing, trial status, trust/compliance docs  

**Production memory stays self-hosted in the customer's VPC.** The portal is the **commercial + trust layer**, not where regulated PHI/PII lives in production.

Fix as much as possible in one pass. Prefer shipping working v1 over perfect automation. Manual fallbacks are OK where noted.

---

## Repo boundaries

| What | Where |
|------|--------|
| PrismCortex product code, benchmarks, licensing | https://github.com/insightitsGit/PrismCortex (public) |
| Marketing site + customer portal | **This workspace** — insightits.com Flask/React production app |
| Do NOT duplicate product logic in the portal | Portal **issues keys** and **links docs**; memory runs in customer infra or trial sandbox |

**Read first in PrismCortex repo (clone or browse GitHub):**

| File | Why |
|------|-----|
| [AGENTS.md](https://github.com/insightitsGit/PrismCortex/blob/master/AGENTS.md) | Canonical URLs, contacts, validated claims |
| [compare.md](https://github.com/insightitsGit/PrismCortex/blob/master/compare.md) | Landing page comparison section — copy blocks, do/don't |
| [infoAlex.md](https://github.com/insightitsGit/PrismCortex/blob/master/infoAlex.md) | Full GTM: pricing, trial flow, page sections, phases A–D |
| [docs/SOC2_ROADMAP.md](https://github.com/insightitsGit/PrismCortex/blob/master/docs/SOC2_ROADMAP.md) | Trust center content — Type I in progress |
| [prismcortex/licensing.py](https://github.com/insightitsGit/PrismCortex/blob/master/prismcortex/licensing.py) | `issue_key()` — Ed25519 offline license |

---

## Architecture (do not confuse buyers)

```
┌─────────────────────────────────────────────────────────────┐
│  Insight ITS Customer Portal (THIS APP)                     │
│  • Login / account                                          │
│  • Licenses & billing (Stripe)                              │
│  • Trial: sandbox URL + trial API key + trial license key   │
│  • Trust center: SOC2 status, security docs, DPA links      │
└─────────────────────────────────────────────────────────────┘
              │
              │  issues offline PRISMCORTEX_LICENSE_KEY
              ▼
┌─────────────────────────────────────────────────────────────┐
│  Customer production (THEIR VPC) — self-hosted              │
│  Docker / pip install prismcortex + license in env          │
│  No phone-home for license verification in prod             │
└─────────────────────────────────────────────────────────────┘

Separate: Trial sandbox on Insight ITS Azure (evaluation only, no prod PHI)
```

**One-liner for UI copy:**

> Production runs in your environment. The portal is for license, billing, trial, and trust documentation.

---

## Work packages — implement in priority order

### WP1 — Product landing page (`/products/prismcortex.html`)

Match layout/style of existing [PrismRAG product page](https://www.insightits.com/products/prismrag.html).

**Sections (top → bottom):**

1. Hero — "Agent memory your auditors can actually trust."  
   CTAs: **Start 30-Day Validation** (primary) · **View benchmark proof** (secondary)
2. Proof bar — **24/24** · **99.6% cache** · **0 errors** · **6 ms replay** · **~20 clients / 4 vCPU**
3. Problem — compliance blocked, drift, third-party memory SaaS rejected
4. How it works — Digest → Consolidate → Recall
5. Library vs HTTP API — two tabs (Python embed vs Docker/curl)
6. **How we compare** — use tables/copy from PrismCortex `compare.md` §2–§3 (Mem0/Zep/RAG)
7. Pricing — from `infoAlex.md` §5 (OSS free, Trial free 30d, Pilot $15k, Pro $32k/yr, Enterprise from $75k, Founding $45k/yr first 5)
8. Trial block — limits, "evaluation only, no production PHI" disclaimer
9. Security & compliance — self-hosted prod; SOC2-aligned controls, Type I in progress; link trust center
10. FAQ — honest limits (see Do/Don't below)
11. Final CTA

**Also:**

- [ ] Add product card to homepage "AI Infrastructure Platform" grid
- [ ] Update `sitemap.xml`
- [ ] Add PrismCortex block to `https://www.insightits.com/ai-info.txt`
- [ ] Link GitHub, PyPI, whitepaper, benchmark summary

**Design:** bg `#0f1419`, accent `#5b9bd5` (see PrismCortex audit console palette).

---

### WP2 — Customer portal: PrismCortex product area

Extend the **existing logged-in portal** (same app users use for other Insight ITS products). Do not build a separate portal.

**New nav section:** Products → PrismCortex (or Licenses → PrismCortex)

**Pages / views:**

| View | Content |
|------|---------|
| **Overview** | Plan tier, status (trial / active / expired), expiry date, quick links |
| **License key** | Display `PRISMCORTEX_LICENSE_KEY` with copy button; explain paste into customer env |
| **Trial sandbox** | If on trial: sandbox URL, API key, link to `/console`, curl examples |
| **Billing** | Stripe customer portal link or embedded invoices; plan upgrade CTA |
| **Trust & compliance** | SOC2 status, security overview, links to GitHub SECURITY.md, subprocessors, DPA request |
| **Deploy guide** | pip install, Docker, env vars — link to GitHub README |

**Data model (extend existing user/org tables):**

```text
product_entitlements:
  user_id / org_id
  product: "prismcortex"
  tier: oss | trial | pilot | pro | enterprise
  license_key: text (encrypted at rest)
  license_expires_at: timestamp
  features: json array
  trial_api_key_hash: optional
  trial_sandbox_url: optional
  stripe_subscription_id: optional
  created_at, updated_at
```

Reuse existing Stripe customer ID if the app already has one.

---

### WP3 — 30-day validation trial flow

**Entry:** Landing page CTA → `/products/prismcortex/trial` or portal signup if logged in.

**Form fields:**

- Work email, name, company, role (dropdown), use case, regulated-industry checkbox
- Agree ToS + **"I will not put production PHI/PII in the trial sandbox"** checkbox

**On submit (automate what you can; manual queue OK v1):**

1. Create org + user if needed; log into portal
2. Generate trial entitlement: `tier=trial`, 30-day expiry, features=`[console, recall_at, replay_certificate]`
3. Issue license key via `issue_key()` from PrismCortex licensing (see WP5 — private key server-side only)
4. Generate scoped trial API key; store hash in DB
5. Assign sandbox URL (see WP4) — or placeholder + "provisioning within 24h" if sandbox not live yet
6. Send welcome email: keys, curl snippet, link to portal + `/console`
7. Schedule Day 25 reminder + Day 30 expiry job

**Limits (enforce when sandbox exists):**

- 30 calendar days
- 1,000 digest + 5,000 recall / day
- 5,000 facts max
- 1 tenant
- Max 3 trials per company email domain per quarter

**Manual fallback v1:** Form saves to admin queue → email info@insightits.com → ops issues keys within 24h. Still show pending state in portal.

---

### WP4 — Trial sandbox (Azure)

If you have Azure deploy access in this workspace or a deploy repo:

1. Deploy PrismCortex server container (reuse patterns from PrismCortex `deploy/run_only.sh`)
2. HTTPS URL: `https://prismcortex-demo.insightits.com` (or existing Azure FQDN)
3. Env: per-trial API keys in `PRISMCORTEX_API_KEYS` JSON or DB-backed middleware
4. Cron: revoke expired keys; delete expired tenant data at day 30

If sandbox deploy is out of scope, ship portal + landing with **"Trial provisioning — contact within 24h"** and wire sandbox later.

---

### WP5 — License issuance (secure)

**Mechanism:** PrismCortex `prismcortex/licensing.py` — Ed25519, offline verify, no phone-home.

```python
from prismcortex.licensing import issue_key

key = issue_key(
    private_key_hex=os.environ["PRISMCORTEX_LICENSE_PRIVATE_KEY"],  # NEVER in frontend
    tier="pro",  # or trial, enterprise, pilot
    expiry_iso="2027-06-30T00:00:00+00:00",
    customer="Acme Corp",
    features=["console", "recall_at", "multi_tenant", "legal_hold"],
)
```

**Requirements:**

- [ ] Generate production keypair if not done (`generate_keypair()` on secure machine)
- [ ] Store **private key** in app secrets (Azure Key Vault / env — never commit)
- [ ] Update PrismCortex repo public verify key when rotating (coordinate separate PR)
- [ ] Admin endpoint or Stripe webhook calls issuer; returns key to portal + email

**Tier → features map** (from `infoAlex.md` §5):

| Tier | Features |
|------|----------|
| trial | console, recall_at, replay_certificate |
| pilot | same as trial + extended expiry per contract |
| pro | console, recall_at, replay_certificate, multi_tenant (≤5), legal_hold |
| enterprise | all commercial + negotiated SLA |

---

### WP6 — Stripe / paid checkout

Follow existing Stripe patterns in the production app.

| Plan | Stripe approach |
|------|-----------------|
| Validation Trial | Free — no Stripe |
| Compliance Pilot | $15,000 one-time Checkout or invoice |
| Pro | $32,000/yr — subscription or invoice |
| Enterprise | **Contact sales only** — no self-serve $75k checkout |
| Founding Enterprise | $45,000/yr — manual contract + Stripe invoice |

**Webhook `checkout.session.completed`:**

1. Map price ID → tier
2. Issue with `issue_key()` (1-year expiry unless pilot)
3. Save to `product_entitlements`
4. Email license + link to portal deploy guide

Pilot: note 100% credit to Year 1 if convert within 90 days (manual ops OK).

---

### WP7 — Trust & compliance center (portal)

Centralize what enterprise buyers ask for — **org-level**, covers portal + trial sandbox:

| Document / status | Source | Display |
|-------------------|--------|---------|
| SOC 2 Type I | In progress | Status badge + expected timeline; **not "certified"** |
| Security overview | Link PrismCortex SECURITY.md + app security page | PDF or linked |
| Penetration test | Not done yet | "Scheduled" / "In progress" — honest |
| Subprocessors | Insight ITS list | Table |
| DPA / BAA | Legal templates | Request form or download |
| Benchmark proof | GitHub RESULTS.md | Link + optional PDF |

Copy safe language from `docs/SOC2_ROADMAP.md`:

> SOC 2-aligned controls (access, audit, erasure, tenant isolation). Type I attestation in progress.

---

## Validated claims — SAFE to use

Pull numbers only from GitHub `benchmarks/RESULTS.md` and `compare.md`:

- **24/24** byte-identical replays (Azure E2E, real Gemini, v0.2.1)
- **$40k → $55k** correction; superseded fact retained
- **99.6%** cache hit rate (30 Gemini / 2,563 recalls)
- **~6 ms** cached replay vs **~724 ms** first render
- **0 server errors** on core path
- **Mixed load c=20, 0 errors** on 4 vCPU node
- **~20 concurrent clients / 4 vCPU** reference sizing
- Head-to-head vs Mem0 OSS: correction test surfaced **$55k** (PrismCortex) vs stale **$40k** top hit (Mem0) — narrow live test, not LoCoMo leaderboard

---

## Do NOT claim (legal/marketing)

| Never say | Say instead |
|-----------|-------------|
| SOC 2 certified | SOC 2-aligned controls; Type I in progress |
| We beat Mem0 on LoCoMo | Full LoCoMo run pending; lead on compliance/replay/audit |
| 50 concurrent clients, zero errors | ~20 clients / 4 vCPU validated; c=50 is stress-only |
| Hosted production for regulated PHI/PII | Trial sandbox for evaluation; production self-hosted |
| Mem0 can't handle corrections | Our narrow retrieval test vs their LongMemEval benchmarks |
| Customer logos | Azure-validated benchmarks |

---

## CTAs — wire these everywhere

| Button | Destination |
|--------|-------------|
| Start 30-Day Validation | Trial form → portal |
| View benchmark proof | GitHub RESULTS.md or hosted PDF |
| Install OSS Core | PyPI + GitHub |
| Start Compliance Pilot | Stripe or contact sales $15k |
| Talk to Enterprise | info@insightits.com |
| Book Agent Memory Audit | Calendly or mailto |

---

## Canonical URLs (use exactly)

| Resource | URL |
|----------|-----|
| GitHub | https://github.com/insightitsGit/PrismCortex |
| PyPI | https://pypi.org/project/prismcortex/ |
| Product page | https://www.insightits.com/products/prismcortex.html |
| Trial signup | https://www.insightits.com/products/prismcortex/trial |
| Trial sandbox (target) | https://prismcortex-demo.insightits.com |
| Company | https://www.insightits.com |
| Contact | info@insightits.com · +1 (973) 692-6919 |

---

## Definition of done (fix as much as you can)

**Minimum shippable:**

- [ ] Landing page live with comparison section + proof bar + pricing + honest FAQ
- [ ] Homepage product card + sitemap + ai-info.txt updated
- [ ] Logged-in portal shows PrismCortex license section (even if manual key paste from admin v1)
- [ ] Trial signup form saves request + sends confirmation email
- [ ] Trust tab with honest SOC2/pen-test status

**Stretch:**

- [ ] Automated trial key issuance + portal display
- [ ] Stripe webhook → license for Pilot/Pro
- [ ] Trial sandbox deployed and linked from portal
- [ ] Day 25/30 lifecycle emails + expiry cron

**Out of scope / do not fake:**

- SOC 2 Type I certificate (doesn't exist yet)
- Full LoCoMo benchmark run
- Production hosted memory SaaS for customer PHI

---

## Implementation notes

1. **Match existing patterns** — inspect how PrismRAG or other products handle portal entitlements and Stripe; clone that structure for `product: "prismcortex"`.
2. **Secrets** — `PRISMCORTEX_LICENSE_PRIVATE_KEY`, `GEMINI_API_KEY` (trial sandbox only), Stripe keys — env/Key Vault only.
3. **No phone-home** — production license verification stays offline in customer's PrismCortex deployment; portal only **delivers** the key string.
4. **Mobile** — comparison table as stacked cards on small screens.
5. **Commit message style** — short imperative: "Add PrismCortex portal entitlements and landing page"
6. **Ask before push** if user hasn't granted permission.

---

## Contact

Insight IT Solutions LLC · info@insightits.com · 39 Aliso Ridge Loop, Mission Viejo, CA 92691, US

*Prompt version: 2026-06-30 · Source: PrismCortex repo AGENTS.md, compare.md, infoAlex.md*
