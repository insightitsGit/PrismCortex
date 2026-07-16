# PrismCortex — NotebookLM Story Source

> **How to use this file in NotebookLM**
>
> 1. Go to [notebooklm.google.com](https://notebooklm.google.com)
> 2. Create a new notebook titled **PrismCortex**
> 3. Upload this file (`docs/NOTEBOOKLM_STORY.md`) as a source
> 4. Optionally add: `README.md`, `docs/WHITEPAPER.md`, `benchmarks/RESULTS.md`
> 5. Click **Audio Overview** to generate a podcast-style story, or ask:
>    - “Explain PrismCortex to a compliance officer”
>    - “How do I install and use PrismCortex?”
>    - “How does PrismCortex compare to Mem0 and Zep?”
>    - “Give me a sales pitch for regulated B2B”
>
> **Last updated:** 2026-06-30 · v0.2.1 · Insight IT Solutions LLC

---

# Part 1 — The story (what is PrismCortex?)

Imagine you’re a VP of Engineering at a bank. Legal just blocked your AI agent launch. Not because the model is bad — because **nobody can prove what the agent knew last Tuesday**, or whether a budget correction from forty thousand to fifty-five thousand dollars was actually reflected in answers, or whether old values were silently erased.

That’s the problem **PrismCortex** solves.

PrismCortex is **compliance-grade memory for AI agents**. It is not another vector database. It is not a chat log. It is a **self-hosted memory engine** that turns conversation into a **knowledge graph**, consolidates uncertain facts in the background, and recalls answers in a way auditors can **replay, time-travel, and explain**.

The company behind it is **Insight IT Solutions LLC**, based in Mission Viejo, California. The product is open-core on PyPI (`pip install prismcortex`), with a public GitHub repository at **github.com/insightitsGit/PrismCortex**.

The one-line pitch:

> **Ship AI agents that regulators can audit — byte-identical replay, bitemporal history, and corrections that never silently erase the past.**

---

# Part 2 — Why existing approaches fail

Most agent memory today falls into three buckets — and all three break in regulated production.

**Append-only chat logs** store every message forever. When legal asks “what did the agent know on March 3rd?”, you grep JSON. That’s not evidence. That’s archaeology.

**Vector RAG** retrieves similar chunks. Similarity is not proof. A correction might not rank high enough to surface. Old facts may disappear from retrieval even if they’re still “somewhere” in the store.

**Third-party memory SaaS** (Mem0 Platform, Zep Cloud, and others) can be excellent for speed-to-market — but compliance teams often reject them for **data residency**, subprocessors, and audit requirements.

PrismCortex’s wedge is different: **compliance, audit, and sovereignty** — not “remember that the user likes pizza.”

---

# Part 3 — How PrismCortex works (the three verbs)

Every integration boils down to three operations:

## Digest

Each conversation turn goes through a **salience gate**. Low-value chatter (“ok thanks”, “got it”) is skipped with **zero LLM calls**. Valuable facts are extracted into a **knowledge graph** — the gist, not the raw log.

Example input: *“Our production deploy budget is $40,000 per quarter.”*

The graph stores structured facts — subject, relation, object — not a verbatim transcript.

## Consolidate (sleep)

Uncertain or conflicting facts go to a **staging buffer**. A background `sleep()` pass resolves conflicts, merges entities carefully, and commits when confident. Urgent corrections (marked as alerts) can **fast-track** inline.

This mimics biological memory: some things commit immediately; others consolidate overnight.

## Recall

When the agent needs an answer, PrismCortex **retrieves a subgraph** of relevant facts and uses the LLM as a **renderer only** — to turn facts into natural language **once**. The rendered answer is frozen in a **content-addressed cache**.

The second time you ask the same question at the same memory version, you get **byte-identical replay** from cache — not a fresh LLM call.

### The famous demo

```python
from prismcortex import reference_memory

mem = reference_memory()

mem.digest("My production deploy budget is $40,000.")
print(mem.recall("What's my deploy budget?").answer)
# → "$40,000"

mem.digest("Correction: my deploy budget is now $55,000.")
print(mem.recall("What's my deploy budget?").answer)
# → "$55,000"

# The $40,000 fact is STILL in the audit trail — time-stamped, queryable.
```

This correction scenario was validated on **Azure with real Gemini**: the answer changed, and the superseded fact was retained. That’s **bitemporal audit** — invalidate old, add new, **keep history**.

---

# Part 4 — How to use PrismCortex (technical quickstart)

## Requirements

- Python 3.10+
- For real extraction/rendering: `GEMINI_API_KEY`
- For production HTTP: `PRISMCORTEX_API_KEY`

## Install options

```bash
pip install prismcortex                      # MIT open core
pip install "prismcortex[gemini]"            # + Gemini extraction
pip install "prismcortex[server]"            # + FastAPI HTTP service
pip install "prismcortex[prism]"             # + full Insight ITS stack
pip install "prismcortex[gemini,server,prism]"  # production stack
```

## Option A — Python library (single agent, in-process)

Best for embedding memory directly in your Python agent:

```python
from prismcortex import reference_memory

mem = reference_memory()  # set GEMINI_API_KEY in environment

mem.digest("We use Postgres 16 in us-east-1.")
result = mem.recall("Where is our database hosted?")

print(result.answer)       # natural language answer
print(result.cache_hit)    # True after first render
print(result.confidence)   # retrieval confidence
```

## Option B — HTTP service (multi-agent, any language)

Best for platform teams, Docker, Kubernetes, Azure:

```bash
export GEMINI_API_KEY=your-key
export PRISMCORTEX_API_KEY=your-secret
uvicorn prismcortex.server:app --host 0.0.0.0 --port 8080
```

OpenAPI docs at `http://localhost:8080/docs`.

```bash
# Ingest a fact
curl -X POST http://localhost:8080/digest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret" \
  -d '{"text": "Our deploy budget is $40,000."}'

# Recall an answer
curl -X POST http://localhost:8080/recall \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret" \
  -d '{"query": "What is our deploy budget?"}'
```

## Docker and Azure

The repo includes a `Dockerfile` and deploy scripts (`deploy/run_only.sh`) for Azure Container Instances. The Azure benchmark runs **two containers in the same zone**: one server, one driver — proving memory works over the network, not just in-process.

## Key enterprise endpoints (commercial license)

| Endpoint | Purpose |
|----------|---------|
| `POST /explain` | Evidence trail — which facts supported this answer |
| `POST /recall_at` | Time-travel recall as of a past timestamp |
| `GET /replay_certificate` | Auditor-ready replay proof |
| `GET /conflicts` | Surface contested facts — never silently serve conflicts |
| `POST /forget` | GDPR erasure with tombstones |
| `POST /legal_hold` | Block erasure for litigation |
| `GET /console` | Audit console UI |
| `GET /metrics` | Ops metrics |

Auth on all endpoints: header `X-API-Key`.

---

# Part 5 — Architecture (for technical audiences)

PrismCortex orchestrates the **Insight ITS stack** behind one API:

| Layer | Package | Role |
|-------|---------|------|
| Projection | PrismLang | Deterministic text → embedding |
| Graph | PrismRAG | Bitemporal knowledge store |
| Consolidation | PrismResonance | Salience, decay, sleep() |
| Cache | PrismLib | Content-addressed render cache |
| Orchestration | **PrismCortex** | Versioning, staging, determinism contract |

### Two-speed memory

- **Fast path:** certain facts and urgent corrections commit immediately (version increments).
- **Slow path:** uncertain facts stage → `sleep()` consolidates → commit.

### Determinism (honest version)

PrismCortex does **not** claim “temperature zero means identical LLM output” from shared APIs.

It claims **replay determinism**: once an answer is rendered for a `(query, memory-version)` pair, it is **frozen** and replayed **byte-identically**. Cache key includes query, subgraph version, template, and model snapshot.

### Scale

With ANN enabled (`PRISMCORTEX_USE_ANN=1`):

- **50,000 facts** → 85% hit@8, **74 ms** p95 retrieval (benchmark, no LLM)
- **10,000 facts** → 91.5% hit@8, 10 ms p95

### Sizing (production reference)

Validated on Azure: **~20 concurrent clients per 4 vCPU node**, mixed read/write, **zero errors**. Reference load SLO **passes** at c=20. Optional stress at c=50 is a ceiling probe only.

---

# Part 6 — Proof (what we measured on Azure)

**Badge line:** Azure-validated · real Gemini · v0.2.1 · June 2026

| Metric | Result |
|--------|--------|
| Byte-identical replay | **24/24** |
| Correction + audit | **$40k → $55k**; old fact retained |
| Cache hit rate | **99.6%** (30 Gemini calls / 2,563 recalls) |
| Cached replay latency | **~6 ms** vs **~724 ms** first render |
| Throughput (cached, c=20) | **141 req/s** |
| Mixed load @ c=20 | **0 errors** |
| Server errors (core path) | **0** |
| Memory plateau (675 chatter turns) | Graph stayed flat — 0 new edges |
| Gist vs raw log | **5.2×** smaller |

All numbers reproducible from GitHub: `benchmarks/RESULTS.md` and `benchmarks/results/results.json`.

---

# Part 7 — How we compare (marketing + competitive)

**Positioning in one sentence:**

> Mem0 and Zep win published accuracy benchmarks. PrismCortex wins **compliance** — byte-identical replay, bitemporal audit, and self-hosted sovereignty.

| | Mem0 | Zep | PrismCortex |
|---|------|-----|-------------|
| LoCoMo accuracy | 91.6% (published) | — | Full run pending |
| Byte-identical replay | No | No | **Yes (24/24)** |
| Bitemporal audit (OSS) | Varies | Graph | **Yes** |
| Self-hosted default | OSS + SaaS | SaaS | **Yes** |
| Evidence / replay cert | Limited | Graph context | **/explain, /replay_certificate** |

### Live head-to-head vs Mem0 OSS

Same Gemini, same correction test ($40k → $55k):

- **PrismCortex:** surfaced $55k; kept $40k in audit trail; byte-identical on replay
- **Mem0 OSS:** top retrieval stayed on $40k in our live test

**Honest caveat:** Mem0 reports 96.2% knowledge-update on LongMemEval — they handle corrections in their benchmark suite. Our test is a narrow retrieval comparison, not a leaderboard claim.

### What PrismCortex is NOT

- Not “we beat Mem0 on LoCoMo” (full run not published yet)
- Not “cheaper Mem0” or generic “better RAG”
- Not hosted production SaaS for regulated PHI/PII (trial sandbox only)
- Not SOC 2 certified yet (Type I in progress; controls aligned)

---

# Part 8 — Who it’s for (marketing personas)

**Primary buyer:** VP Engineering, Head of AI Platform, or Chief Compliance Officer at **regulated B2B** — finance, insurance, healthcare, legal, government.

**Pain:** Legal blocks agents because memory is a black box. Third-party memory SaaS fails data residency review. Corrections don’t leave an audit trail.

**Dream outcome:** Pass compliance review and ship production agents in 30–90 days with memory auditors can **replay, time-travel, and explain** — self-hosted in the customer’s region.

**Industries:**

- Banks and fintech (policy changes, audit trails)
- Insurance (claim decisions, regulatory replay)
- Healthcare (PHI stays in customer VPC — not in trial sandbox)
- Legal tech (matter history, time-travel)
- Government and defense (air-gapped, offline license)

---

# Part 9 — Pricing and go-to-market

## Offer ladder

| Plan | Price | Best for |
|------|-------|----------|
| **OSS Core** | Free (MIT) | Developers, dev PoC |
| **30-Day Validation Trial** | Free | Try replay + audit console on Insight ITS sandbox |
| **Compliance Pilot** | $15,000 one-time | Staging on customer infra; 100% credit to Year 1 if convert in 90 days |
| **Pro** | $32,000/year | Single production deployment, ≤5 tenants |
| **Enterprise** | from $75,000/year | Regulated production, 24×7 support |
| **Founding Enterprise** | $45,000/year (first 5 customers) | Design partner pricing, locked 2 years |

## Two deployment modes

| Mode | Where | Purpose |
|------|-------|---------|
| **Validation trial** | Insight ITS Azure sandbox | Evaluation only — no production PHI |
| **Production** | Customer VPC / region | Self-hosted Docker or library + offline license key |

**Critical message:** Production memory lives in **the customer’s environment**. The customer portal (insightits.com) handles license, billing, and trust docs — not where regulated data lives in production.

## Commercial license

Commercial features use an **offline Ed25519 license key** — no phone-home. Customer sets `PRISMCORTEX_LICENSE_KEY` in their deployment. Required for audit console, time-travel, multi-tenant governance at scale.

## ROI story

- 6-month launch delay ≈ $400,000 opportunity cost
- Excess LLM re-extraction ≈ $8,000/month
- Founding Enterprise ≈ $45,000/year
- Payback if compliance unblocks launch: **under 2 months**

## Pilot guarantee

> Byte-identical replay certificates on ≥3 agreed audit queries within 14 days on staging, or full pilot fee refunded.

---

# Part 10 — Related Insight ITS products

PrismCortex sits in the **Insight ITS AI Infrastructure Platform** alongside:

| Product | URL | Role |
|---------|-----|------|
| **PrismRAG** | insightits.com/products/prismrag.html | Governed enterprise RAG |
| **PrismLang** | insightits.com/products/prismlang.html | Deterministic projection |
| **PrismResonance** | insightits.com/products/prism-resonance.html | Wavepacket memory / consolidation |
| **CHORUS Fabric** | insightits.com/products/chorus-fabric.html | Agent mesh protocol |

PrismCortex is the **orchestration layer** that unifies digest/recall for agent memory across this stack.

---

# Part 11 — Security and compliance notes

- **Self-hosted production** — customer controls data residency
- **SOC 2-aligned controls** implemented (auth, RBAC, audit logs, erasure, tenant isolation)
- **SOC 2 Type I attestation in progress** — do not claim certified until report exists
- **Penetration test** — planned, not complete
- **SBOM** generated per release
- **Security contact:** info@insightits.com (do not file public GitHub issues for vulnerabilities)
- **Trial sandbox:** evaluation only; no production PHI/PII without BAA/DPA

---

# Part 12 — FAQ (honest answers)

**Q: Is this just RAG?**  
A: No. RAG retrieves chunks. PrismCortex builds a bitemporal graph, renders once, caches deterministically, and provides audit APIs.

**Q: Does temperature 0 guarantee identical answers?**  
A: No — not with shared APIs. PrismCortex guarantees **replay** determinism after first render.

**Q: Can I use it without Gemini?**  
A: The open core runs with hashing embeddings for dev/tests. Production uses Gemini (`[gemini]` extra) or the full Prism stack (`[prism]`).

**Q: How does it compare to Mem0?**  
A: Mem0 leads accuracy benchmarks and SaaS maturity. PrismCortex leads compliance: replay certificates, bitemporal OSS audit, self-hosted sovereignty.

**Q: How many concurrent users per server?**  
A: Reference sizing: **~20 concurrent clients per 4 vCPU node** (validated). Scale reads horizontally with replicas.

**Q: Is there a free trial?**  
A: Yes — 30-day validation trial on Insight ITS hosted sandbox (evaluation only).

**Q: Where do I get help?**  
A: info@insightits.com · +1 (973) 692-6919 · GitHub issues for OSS bugs

---

# Part 13 — Canonical links (copy-paste)

| Resource | URL |
|----------|-----|
| GitHub | https://github.com/insightitsGit/PrismCortex |
| PyPI | https://pypi.org/project/prismcortex/ |
| Product page | https://www.insightits.com/products/prismcortex.html |
| Whitepaper | https://github.com/insightitsGit/PrismCortex/blob/master/docs/WHITEPAPER.md |
| Benchmarks | https://github.com/insightitsGit/PrismCortex/blob/master/benchmarks/RESULTS.md |
| Comparison spec | https://github.com/insightitsGit/PrismCortex/blob/master/compare.md |
| AI agent handoff | https://github.com/insightitsGit/PrismCortex/blob/master/AGENTS.md |

**Company:** Insight IT Solutions LLC  
**Address:** 39 Aliso Ridge Loop, Mission Viejo, CA 92691, US  
**Email:** info@insightits.com  
**Phone:** +1 (973) 692-6919

---

# Part 14 — Suggested NotebookLM prompts

After uploading this source, try these prompts in NotebookLM:

1. **“Create a 5-minute audio overview of PrismCortex for a technical founder.”**
2. **“Explain PrismCortex to a bank compliance officer in plain English.”**
3. **“Walk through installing PrismCortex and running the $40k to $55k demo.”**
4. **“Compare PrismCortex to Mem0 and Zep — be honest about strengths and gaps.”**
5. **“Write a landing page hero section and three bullet points for insightits.com.”**
6. **“What should a sales engineer say on a first call with a regulated enterprise?”**
7. **“List what we can claim vs what we must not claim in marketing.”**
8. **“Summarize the Azure benchmark results for an investor deck.”**

---

*This document is the single-source narrative for NotebookLM. For engineering depth, also upload README.md, docs/WHITEPAPER.md, and benchmarks/RESULTS.md from the same repository.*
