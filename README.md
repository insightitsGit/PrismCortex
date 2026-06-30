# PrismCortex

[![PyPI](https://img.shields.io/pypi/v/prismcortex)](https://pypi.org/project/prismcortex/)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/prismcortex)](https://pypi.org/project/prismcortex/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub](https://img.shields.io/github/stars/insightitsGit/PrismCortex?style=social)](https://github.com/insightitsGit/PrismCortex)

**Deterministic, auditable, self-consolidating memory for AI agents.**

Compliance-grade memory for regulated teams: **byte-identical replay**, **bitemporal audit**,
and **self-hosted sovereignty** — not another vector chat log.

**Repository:** https://github.com/insightitsGit/PrismCortex *(public)*

🤖 **[AI agent handoff](AGENTS.md)** · 📄 **[Whitepaper](docs/WHITEPAPER.md)** · 📊 **[Benchmarks](benchmarks/RESULTS.md)** · 🗺️ **[Roadmap](ROADMAP.md)** · 🏗️ **[Design spec](DESIGN.md)**

**Product page:** [insightits.com/products/prismcortex](https://www.insightits.com/products/prismcortex.html)

---

## Why PrismCortex exists

Most agent memory is an append-only chat log or a vector store in someone else's cloud.
That breaks in production when:

- Legal asks *"what did the agent know on March 3rd?"* — and you grep chat logs  
- A correction ($40k → $55k) doesn't reliably surface — or erases audit history  
- Compliance rejects third-party memory SaaS for data residency  

PrismCortex **digests** each turn into a knowledge graph, **consolidates** uncertain facts
in the background (`sleep()`), and **recalls** by rendering facts once and freezing answers
in a content-addressed cache.

```python
from prismcortex import reference_memory

mem = reference_memory(cache_path=".prismcortex_cache/demo.json")

mem.digest("My production deploy budget is $40,000.")
print(mem.recall("What's my deploy budget?").answer)        # → "$40,000"

mem.digest("Correction: my deploy budget is now $55,000.")  # fast-tracked (ALERT)
print(mem.recall("What's my deploy budget?").answer)        # → "$55,000"
# The $40,000 fact is still on record — time-stamped — for audit / time-travel.
```

---

## Validated claims (Azure E2E, real Gemini, v0.2.1)

| Claim | Result |
|-------|--------|
| Replay determinism | **24/24** byte-identical replays |
| Corrections + audit | **$40k → $55k**; superseded fact retained |
| Cost / cache | **99.6% hit rate** — 30 Gemini calls / 2,563 recalls |
| Cached replay | **~6 ms** vs **~724 ms** first render |
| Mixed load (c=20) | **0 errors** on 4 vCPU node |
| Server reliability | **0 errors** on core path |
| Scale (50k facts, ANN) | **85% hit@8**, **74 ms** p95 retrieval |

Details: [benchmarks/RESULTS.md](benchmarks/RESULTS.md) · [docs/WHITEPAPER.md](docs/WHITEPAPER.md)

---

## Install

```bash
pip install prismcortex                  # core (MIT)
pip install "prismcortex[gemini]"        # + real Gemini extraction/rendering
pip install "prismcortex[prism]"         # + full Insight ITS stack (PrismLang, etc.)
pip install "prismcortex[server]"        # + FastAPI HTTP service
pip install "prismcortex[gemini,server,prism]"   # production stack
```

Requires **Python 3.10+**.

---

## Two ways to run

### 1. Python library (in-process)

Best for a single agent embedded in your app:

```python
from prismcortex import reference_memory

mem = reference_memory()   # needs GEMINI_API_KEY for real extraction
mem.digest("We use Postgres 16 in us-east-1.")
result = mem.recall("Where is our database hosted?")
print(result.answer, result.cache_hit, result.confidence)
```

### 2. HTTP service (multi-agent, Docker, Azure)

Best for platform teams and non-Python clients:

```bash
export GEMINI_API_KEY=...
export PRISMCORTEX_API_KEY=your-secret
uvicorn prismcortex.server:app --host 0.0.0.0 --port 8080
# OpenAPI docs: http://localhost:8080/docs
```

```bash
curl -X POST http://localhost:8080/digest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret" \
  -d '{"text": "Our deploy budget is $40,000."}'

curl -X POST http://localhost:8080/recall \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret" \
  -d '{"query": "What is our deploy budget?"}'
```

Docker + Azure deploy: see [deploy/run_only.sh](deploy/run_only.sh).

---

## Why it's different

| | Append-only RAG | PrismCortex |
|---|---|---|
| Storage | every chat turn | graph topology (the *gist*) |
| Updates | append + hope retrieval ranks it | bitemporal: invalidate old, add new, **keep history** |
| Determinism | logs + LLM drift | content-addressed cache, **replay-identical** |
| Cost | re-extract every call | salience-gated writes, **cached reads** |
| Audit | grep the logs | evidence trail + **replay certificate** |

---

## Enterprise features (v0.2)

| Feature | Endpoint / module |
|---------|-------------------|
| Explainability | `POST /explain` |
| Time-travel recall | `POST /recall_at` |
| Replay certificate | `GET /replay_certificate` |
| Conflict surfacing | `GET /conflicts`, `POST /conflicts/resolve` |
| GDPR erasure | `POST /forget` |
| Legal hold | `POST /legal_hold` |
| Multi-tenant + RBAC | `auth.py`, `tenant.py` |
| Audit console | `GET /console` |
| Metrics / ops | `GET /metrics`, `GET /dashboard` |
| 50k+ facts (ANN) | `PRISMCORTEX_USE_ANN=1` |

Docs: [docs/SLA.md](docs/SLA.md) · [docs/CAPACITY.md](docs/CAPACITY.md) · [docs/SOC2_ROADMAP.md](docs/SOC2_ROADMAP.md) · [SECURITY.md](SECURITY.md)

---

## Architecture

```
digest(text) ─▶ salience gate ─▶ extract gist ─▶ delta in RAM
                   ├─ certain / urgent ─▶ commit  (version++)
                   └─ uncertain ───────▶ staging buffer ──▶ sleep() ──▶ commit

recall(query) ─▶ retrieve subgraph ─▶ cache hit? replay (byte-identical)
                                    └─ miss? render once → freeze
```

| Port | Reference | Production (`[prism]`) |
|------|-----------|----------------------|
| Gist projection | hashing embeddings | `prismlang` |
| Graph store | in-memory bitemporal | `prismrag-patch` |
| Consolidation | in-process | `prismresonance` |
| Render cache | JSON file | `prismlib` |
| Extraction | — | Gemini (`[gemini]`) |

Full design: [DESIGN.md](DESIGN.md) · Whitepaper: [docs/WHITEPAPER.md](docs/WHITEPAPER.md)

---

## Determinism, honestly

We do **not** claim "temperature 0 = identical output" for shared API models.

We claim **replay determinism**: once an answer is rendered for a `(query, memory-version)`
pair, it is frozen and replayed byte-identically. Facts are extractive from the graph;
prose is frozen after first render. See [DESIGN.md §2](DESIGN.md#2-the-determinism-model-the-honest-version).

---

## Development & benchmarks

```bash
git clone https://github.com/insightitsGit/PrismCortex.git
cd PrismCortex
pip install -e ".[dev,gemini,server]"

pytest tests/test_graph_engine.py          # no API key
GEMINI_API_KEY=... pytest                  # full suite

python benchmarks/scale_bench.py --ann     # 50k ANN scale test
BACKEND=prism bash deploy/run_only.sh      # Azure E2E (needs .env)
```

Publish to PyPI: `scripts/publish_pypi.ps1` (requires `PYPI_API_TOKEN`).

---

## Documentation index

| Doc | Contents |
|-----|----------|
| [AGENTS.md](AGENTS.md) | **AI agent handoff** — canonical URLs, contacts, processes |
| [ai-info.txt](ai-info.txt) | Machine-readable product summary for LLM crawlers |
| [docs/WHITEPAPER.md](docs/WHITEPAPER.md) | **Product whitepaper** — problem, architecture, validation |
| [DESIGN.md](DESIGN.md) | Engineering design spec |
| [benchmarks/RESULTS.md](benchmarks/RESULTS.md) | Azure benchmark scorecard |
| [ROADMAP.md](ROADMAP.md) | Enterprise GA plan + honest gaps |
| [docs/SLA.md](docs/SLA.md) | Reference SLOs + commercial tiers |
| [docs/CAPACITY.md](docs/CAPACITY.md) | Sizing guide (~20 concurrent clients / 4 vCPU) |
| [docs/LOAD_BENCHMARK.md](docs/LOAD_BENCHMARK.md) | **Load test explainer** — what we fixed, how to read SLO fields |
| [docs/SCALING.md](docs/SCALING.md) | Horizontal read scaling story |
| [docs/SUPPORT.md](docs/SUPPORT.md) | 24×7 Enterprise support model |
| [docs/SOC2_ROADMAP.md](docs/SOC2_ROADMAP.md) | Compliance readiness |
| [SECURITY.md](SECURITY.md) | Security posture |

---

## Licensing

**Open-core (MIT):** `digest`/`recall`, bitemporal graph, determinism cache — free on PyPI.

**Commercial:** audit console, advanced governance, scale tiers — **offline Ed25519 license key**,
no phone-home, air-gap friendly. See [DESIGN.md §7](DESIGN.md#7-packaging--licensing-open-core-self-hosted).

Enterprise: [info@insightits.com](mailto:info@insightits.com) · +1 (973) 692-6919 · [Insight IT Solutions LLC](https://www.insightits.com)  
Address: 39 Aliso Ridge Loop, Mission Viejo, CA 92691, US

---

## Related Insight ITS products

PrismCortex orchestrates the Insight ITS stack. Related products:

- [PrismRAG](https://www.insightits.com/products/prismrag.html) — governed enterprise RAG  
- [PrismLang](https://www.insightits.com/products/prismlang.html) — deterministic projection  
- [PrismResonance](https://www.insightits.com/products/prism-resonance.html) — wavepacket memory  
- [CHORUS Fabric](https://www.insightits.com/products/chorus-fabric.html) — agent mesh protocol  
