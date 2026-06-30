# Support & operations (Enterprise)

PrismCortex is **self-hosted** — you operate the infrastructure; we provide software, patches,
and support per tier. This document defines the **24×7 Enterprise support model** Insight IT
Solutions commits to on signed Enterprise contracts.

---

## Support tiers

| Tier | Hours | Channels | P1 response | Target audience |
|---|---|---|---|---|
| **Standard** | Business hours (Mon–Fri, 9–5 US Eastern) | Email | Best effort &lt; 4 h | Pilots, internal teams |
| **Enterprise** | **24×7×365** for P1 production outage | Email + secure ticket portal + phone bridge (P1) | **1 hour acknowledge**, 4 h mitigation plan | Regulated production |

Standard tier: see [SLA.md](SLA.md). Enterprise tier includes negotiated uptime/credit language
on **your** deployment (we do not host SaaS uptime).

---

## Severity definitions

| Severity | Definition | Examples |
|---|---|---|
| **P1 — Critical** | Production memory service down or data integrity at risk | All `/recall` 5xx; graph corruption; auth bypass |
| **P2 — High** | Major feature degraded, no workaround | Digest failures &gt; 10%; tenant isolation breach |
| **P3 — Medium** | Degraded with workaround | Elevated latency; single-tenant issue |
| **P4 — Low** | Question, docs, enhancement | Integration guidance, feature request |

---

## 24×7 escalation path (Enterprise)

```
Customer opens ticket (email / portal)
        │
        ▼
L1 Support Engineer — acknowledge ≤ 1 h (P1)
        │  runbook triage: /health, /metrics, logs
        ▼
L2 Platform Engineer — if not resolved in 4 h (P1)
        │  engine, cache, Gemini integration
        ▼
L3 Engineering Lead — data integrity, security, release patch
        │
        ▼
Executive bridge — customer-visible outage &gt; 8 h (P1)
```

**On-call rotation:** primary + secondary engineer, weekly rotation, PagerDuty (or equivalent)
for P1 pages. Maintenance windows communicated **72 h** in advance.

---

## What we support

| In scope | Out of scope |
|---|---|
| PrismCortex server, engine, documented APIs | Customer LLM provider outages (Gemini/OpenAI) |
| Upgrade / patch guidance | Customer K8s/ACI misconfiguration |
| Capacity sizing per [CAPACITY.md](CAPACITY.md) | Third-party vector DB unless contracted PS |
| Security patch releases | Pen-test remediation in customer infra |

---

## Release & patch SLAs (Enterprise)

| Item | Commitment |
|---|---|
| **Security patches** (CVE in PrismCortex deps) | Critical: **7 calendar days**; High: **30 days** |
| **Bugfix releases** | Monthly cadence + hotfix for P1 data-integrity bugs |
| **Major releases** | Quarterly (see SLA.md) |

---

## Professional services (optional)

- Entity ontology / alias mapping for customer domains
- Integration with internal agent frameworks
- Compliance mapping workshops (SOC 2 customer audit support)
- Load-test validation on customer-shaped hardware

Contact: Insight IT Solutions LLC — see README.

---

## Customer responsibilities (self-hosted)

- TLS termination, network policy, secrets rotation ([KEY_ROTATION.md](KEY_ROTATION.md))
- Backup of `PRISMCORTEX_DATA` and tenant stores
- Operating `/health` and `/metrics` in your monitoring stack ([OPS_RUNBOOK.md](OPS_RUNBOOK.md))
- Sizing per **~20 concurrent clients / 4 vCPU node** ([SLA.md](SLA.md))
