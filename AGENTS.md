# PrismCortex — AI agent handoff

> **Audience:** AI coding agents, website builders, sales ops, and automation that need
> accurate URLs, contacts, and step-by-step processes without guessing.
> **Read this file first** before changing docs, deploying, or building insightits.com pages.

---

## 1. Canonical identity

| Field | Value |
|-------|-------|
| **Product** | PrismCortex — compliance-grade agent memory |
| **Version** | v0.2.1 (PyPI + Azure benchmarks) |
| **Owner** | Insight IT Solutions LLC |
| **Email** | info@insightits.com |
| **Phone** | +1 (973) 692-6919 |
| **Address** | 39 Aliso Ridge Loop, Mission Viejo, CA 92691, US |
| **Company site** | https://www.insightits.com |
| **Product page** | https://www.insightits.com/products/prismcortex.html *(create if missing)* |
| **License** | MIT open core + offline Ed25519 commercial key (no phone-home) |

---

## 2. Canonical URLs (all public)

| Resource | URL | Notes |
|----------|-----|-------|
| **GitHub repository** | https://github.com/insightitsGit/PrismCortex | **PUBLIC** since 2026-06-29 |
| **Default branch** | `master` | |
| **PyPI package** | https://pypi.org/project/prismcortex/ | `pip install prismcortex==0.2.1` |
| **Whitepaper (repo)** | https://github.com/insightitsGit/PrismCortex/blob/master/docs/WHITEPAPER.md | |
| **Benchmark scorecard** | https://github.com/insightitsGit/PrismCortex/blob/master/benchmarks/RESULTS.md | |
| **OpenAPI (when server running)** | `http://<host>:8080/docs` | FastAPI auto-docs |
| **Trial sandbox (planned)** | https://prismcortex-demo.insightits.com | Not live until Phase C in infoAlex.md |
| **Trial signup (planned)** | https://www.insightits.com/products/prismcortex/trial | Not live until Phase B |
| **Company ai-info.txt** | https://www.insightits.com/ai-info.txt | Parent org file — add PrismCortex entry there when landing page ships |
| **Issues / bugs** | https://github.com/insightitsGit/PrismCortex/issues | Security: email info@insightits.com privately |

**Do not link to a private or placeholder GitHub URL.** The repo is public at `insightitsGit/PrismCortex`.

---

## 3. Documentation map (read order)

| Priority | File | Purpose |
|----------|------|---------|
| 1 | [AGENTS.md](AGENTS.md) | This file — URLs, contacts, processes |
| 2 | [README.md](README.md) | Developer quickstart, install, API overview |
| 3 | [docs/WHITEPAPER.md](docs/WHITEPAPER.md) | Product whitepaper for buyers and marketing |
| 4 | [infoAlex.md](infoAlex.md) | GTM, landing page spec, trial/pricing, copy bank |
| 5 | [DESIGN.md](DESIGN.md) | Engineering design spec |
| 6 | [benchmarks/RESULTS.md](benchmarks/RESULTS.md) | Azure E2E validation numbers |
| 7 | [ROADMAP.md](ROADMAP.md) | GA gaps and honest maturity |
| 8 | [docs/SLA.md](docs/SLA.md) | Reference SLOs and commercial tiers |
| 9 | [docs/CAPACITY.md](docs/CAPACITY.md) | Sizing (~20 concurrent clients / 4 vCPU) |
| 10 | [SECURITY.md](SECURITY.md) | Security posture |

**Website agents:** use [infoAlex.md](infoAlex.md) §9–§10 for landing page + trial implementation.
**Engineering agents:** use [README.md](README.md) + [DESIGN.md](DESIGN.md) + [deploy/](deploy/).

---

## 4. Product surfaces (both real today)

### A) Python library (in-process)

```python
from prismcortex import reference_memory
mem = reference_memory()  # GEMINI_API_KEY for real extraction
mem.digest("My deploy budget is $40,000.")
mem.recall("What's my deploy budget?").answer
```

### B) HTTP service (multi-agent, Docker, Azure benchmarks)

```bash
pip install "prismcortex[gemini,server]"
export GEMINI_API_KEY=...
export PRISMCORTEX_API_KEY=your-secret
uvicorn prismcortex.server:app --host 0.0.0.0 --port 8080
```

Key endpoints: `POST /digest`, `POST /recall`, `POST /explain`, `GET /replay_certificate`, `GET /console`.
Auth: header `X-API-Key: <key>`.

---

## 5. Processes for AI agents

### 5.1 Clone and develop locally

```bash
git clone https://github.com/insightitsGit/PrismCortex.git
cd PrismCortex
pip install -e ".[dev,gemini,server]"
pytest tests/test_graph_engine.py          # no API key
GEMINI_API_KEY=... pytest                  # full suite
```

### 5.2 Publish to PyPI

1. Bump version in `pyproject.toml` and `prismcortex/__init__.py`.
2. Run tests: `pytest tests/ -q`.
3. Build: `python -m build`.
4. Publish via trusted GitHub Action (`.github/workflows/publish.yml`) on **GitHub Release**,
   or locally: `scripts/publish_pypi.ps1` with `PYPI_API_TOKEN` in `.env` (never commit tokens).
5. Verify: https://pypi.org/project/prismcortex/

### 5.3 Deploy to Azure (benchmark / trial sandbox)

1. Copy `.env.example` → `.env`; set `GEMINI_API_KEY`, Azure credentials.
2. `BACKEND=prism bash deploy/run_only.sh` — builds ACR image, deploys 4 vCPU container, waits for health.
3. Run benchmark: `bash deploy/azure_bench.sh`.
4. Results land in `benchmarks/results/results.json`.

See [deploy/run_only.sh](deploy/run_only.sh), [docs/OPS_RUNBOOK.md](docs/OPS_RUNBOOK.md).

### 5.4 Run scale benchmark (no LLM)

```bash
python benchmarks/scale_bench.py --ann
# Output: benchmarks/results/scale_ann.json
```

### 5.5 Build insightits.com landing page

**Repo boundary:** PrismCortex code lives here; marketing site is a **separate repo** (Flask/React on insightits.com).

1. Read [infoAlex.md](infoAlex.md) §9 (page sections) and §12 (copy bank).
2. Create `products/prismcortex.html` on the **website repo** — not in this repo.
3. Link to public GitHub, PyPI, whitepaper, benchmark PDF.
4. Add PrismCortex block to `https://www.insightits.com/ai-info.txt` and `sitemap.xml`.
5. Trial flow: infoAlex.md §10 Phases B–C (form → keys → sandbox URL).

**Pull proof numbers only from** [benchmarks/RESULTS.md](benchmarks/RESULTS.md) — do not invent stats.

### 5.6 Issue commercial license keys

1. Use `prismcortex/licensing.py` — `generate_keypair()` offline once; keep private key air-gapped.
2. Sign customer payload with expiry + feature flags.
3. Customer sets `PRISMCORTEX_LICENSE_KEY` in their deployment.
4. See [docs/KEY_ROTATION.md](docs/KEY_ROTATION.md).

### 5.7 Commit and push (this repo)

```bash
git status
git add <files>
git commit -m "Short imperative summary"
git push origin master
```

**Never commit:** `.env`, private keys, PyPI tokens, customer license private keys.
**User permission required** before `git push` unless explicitly asked.

---

## 6. Validated claims (safe to cite)

| Claim | Evidence |
|-------|----------|
| 24/24 byte-identical replays | Azure E2E v0.2.1 — `benchmarks/RESULTS.md` |
| $40k → $55k correction + history retained | Same |
| 99.6% cache hit (30 Gemini / 2,563 recalls) | Same |
| ~6 ms cached replay vs ~724 ms first render | Same |
| 0 server errors on core path | Same |
| Mixed load c=20, 0 errors on 4 vCPU | Same |
| 50k facts ANN: 85% hit@8, 74 ms p95 | `benchmarks/results/scale_ann.json` |
| ~20 concurrent clients / 4 vCPU node | `docs/CAPACITY.md` |

## 7. Do NOT claim (yet)

| Do not say | Say instead |
|------------|-------------|
| SOC 2 certified | SOC 2-aligned controls; Type I in progress |
| 50 concurrent clients, zero errors | ~20 concurrent clients / 4 vCPU (validated) |
| Hosted production for regulated PHI/PII | Trial sandbox for evaluation; production self-hosted |
| Temperature 0 = identical LLM output | Replay determinism via content-addressed cache |
| GitHub repo is private | Repo is **public** at insightitsGit/PrismCortex |

---

## 8. Related Insight ITS products

| Product | URL |
|---------|-----|
| PrismRAG | https://www.insightits.com/products/prismrag.html |
| PrismLang | https://www.insightits.com/products/prismlang.html |
| PrismResonance | https://www.insightits.com/products/prism-resonance.html |
| CHORUS Fabric | https://www.insightits.com/products/chorus-fabric.html |

PrismCortex orchestrates these packages behind one `digest()` / `recall()` API.

---

## 9. Security contacts

- **Vulnerabilities:** email info@insightits.com — do not open public GitHub issues for security bugs.
- **Trial data:** evaluation sandbox only — no production PHI/PII without BAA/DPA.

---

*Last updated: 2026-06-29 · Maintainer: Insight IT Solutions LLC*
