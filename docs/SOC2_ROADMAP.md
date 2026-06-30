# SOC 2 / ISO 27001 readiness

PrismCortex targets **SOC 2 Type I** readiness for Enterprise buyers, then **Type II** after
12 months of control operation. **Formal attestation is not complete** — this is the procurement
and internal audit artifact until a third-party assessor signs off.

**Related:** [SECURITY.md](../SECURITY.md) · [KEY_ROTATION.md](KEY_ROTATION.md) · [SUPPORT.md](SUPPORT.md)

---

## Current status (2026-06-30)

| Milestone | Status |
|---|---|
| Security controls implemented in product | **Done** (auth, RBAC, audit logs, erasure, rate limits) |
| SBOM generation per release | **Done** (`scripts/generate_sbom.py`) |
| Third-party penetration test | **Not done** — blocker for Type I |
| SOC 2 Type I audit | **Planned** — after pen-test |
| SOC 2 Type II (12 mo evidence) | **Future** |
| ISO 27001 certification | **Future** — map from SOC 2 control set |

---

## Trust Services Criteria mapping (SOC 2)

### CC6 — Logical and physical access

| Control | Implementation | Evidence |
|---|---|---|
| API authentication | `PRISMCORTEX_API_KEY` / scoped JSON keys | `prismcortex/auth.py`, tests |
| Role-based access | read / write / forget / admin roles | server endpoints |
| Input bounds | Pydantic max lengths on digest/recall | `test_server_security.py` |
| License gate | Ed25519 offline verification | `licensing.py` |
| **Gap:** production key rotation | Demo public key still in repo | [KEY_ROTATION.md](KEY_ROTATION.md) |

### CC7 — System operations

| Control | Implementation | Evidence |
|---|---|---|
| Health & metrics | `/health`, `/metrics`, `/dashboard` | Azure E2E, ops runbook |
| Structured audit logs | JSONL `server.jsonl` | `server.py` |
| Request tracing | `trace_id` in logs | `tracing.py` |
| Incident response | 24×7 Enterprise path | [SUPPORT.md](SUPPORT.md) |
| Change management | Git, tagged releases, SBOM | CI + `benchmarks/results/sbom.json` |

### CC8 — Change management

| Control | Implementation | Evidence |
|---|---|---|
| Dependency audit | `pip-audit` clean on core deps | `benchmarks/results/pip_audit.txt` |
| Model epoch pin | `PRISMCORTEX_MODEL` in cache key | deploy scripts |
| **Gap:** pinned lockfile per release | SBOM exists; lock not enforced in CI | release process todo |

### CC9 — Risk mitigation

| Control | Implementation | Evidence |
|---|---|---|
| Prompt injection hardening | Payload delimiters, sanitization | server |
| Digest backpressure | 429 when saturated | capacity guide |
| Legal hold / erasure conflict | Policy engine blocks forget | `policy.py`, tests |
| **Gap:** external pen-test | Required before Type I sign-off | vendor RFP |

### A1 — Availability (customer-operated)

Self-hosted: **customer** owns uptime. We provide:

- Reference SLO from Azure bench ([SLA.md](SLA.md))
- Capacity + scaling guides
- Health alerts (staging backlog, error counts)

### C1 — Confidentiality

| Control | Implementation | Evidence |
|---|---|---|
| Tenant isolation | Separate graph + cache paths per tenant | `tenant.py`, tests |
| Data residency hook | `PRISMCORTEX_REGION` | tenant paths |
| Encryption in transit | **Operator:** TLS at reverse proxy | deployment guide |
| Encryption at rest | **Operator:** disk / volume encryption | deployment guide |

### P1 — Processing integrity (memory correctness)

| Control | Implementation | Evidence |
|---|---|---|
| Deterministic replay | Content-addressed cache | Azure 24/24 PASS |
| Conflict surfacing | `/conflicts`, never silent contested facts | E2E + adversarial |
| Bitemporal audit | Superseded edges retained | reconsolidation bench |

---

## ISO 27001 alignment (high level)

| ISO 27001 Annex A | PrismCortex coverage |
|---|---|
| A.5 Organizational | SUPPORT.md, SLA.md — policies defined |
| A.8 Asset management | SBOM, version tags |
| A.9 Access control | RBAC + API keys |
| A.12 Operations security | OPS_RUNBOOK, logging |
| A.14 System acquisition | pip-audit, SBOM |
| A.18 Compliance | GDPR erasure, legal hold |

Full ISO certification requires ISMS scope statement + external auditor — **not started**.

---

## Path to Type I (ordered)

1. **Replace demo license public key** — operator action
2. **Third-party pen-test** — network + API + auth; remediate findings
3. **Lock release process** — pinned deps + SBOM artifact per tag
4. **Control evidence pack** — export logs, access reviews, on-call roster
5. **Readiness assessment** — SOC 2 consultant / CPA firm
6. **Type I report** — point-in-time design effectiveness

Type II follows **12 months** of operating controls with evidence collection.

---

## What to tell procurement today

> PrismCortex implements SOC-2-aligned controls (access, audit, erasure, tenant isolation)
> suitable for self-hosted regulated deployments. **SOC 2 Type I attestation is in progress**
> pending third-party penetration test and assessor engagement. Enterprise contracts include
> security questionnaire support and roadmap alignment to Type I/II.

Do **not** claim SOC 2 certified until the report exists.
