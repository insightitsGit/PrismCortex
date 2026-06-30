# SLA & support (commercial)

Annual **per-deployment / per-site** license (see DESIGN.md §7). Not metered by token — you host the infra.

---

## Deck-ready one-liners (v0.2.1, Azure-validated)

Use these in pitches and slides. Evidence: [benchmarks/RESULTS.md](../benchmarks/RESULTS.md) (ACR build `ca9`, 2026-06-30).

**Product (what we sell):**

> **Compliance-grade agent memory** — byte-identical replay, bitemporal audit, and corrections that land without wiping history; validated on Azure with real Gemini, zero server errors on the core path.

**Capacity (what one node handles today):**

> On a **single 4 vCPU / 8 GB** node, PrismCortex sustained **mixed read/write at 20 concurrent clients with 0 errors**, **141 cached recalls/sec**, and **99.6% cache hit rate** — ~30 Gemini calls for 2,500+ recalls.

**Cost:**

> **Deterministic cache replay at ~6 ms** vs **~700 ms** first render — the cache is the determinism and the cost story.

**Do not claim yet (until re-validated or scaled out):**

> “50 simultaneous clients per node with zero failures” — burst load at c=50 still showed client-side timeouts in our bench; use **c=20** as the reference concurrency for single-node sizing.

---

## Reference SLO (single node, self-hosted)

Starting points from Azure E2E v0.2.1. Customer SLAs are **negotiated** on Enterprise tier; these are **internal targets** we can defend with artifacts.

| SLO | Target | Validated (v0.2.1) | Notes |
|---|---|---|---|
| Core API availability (bench run) | No unhandled 5xx on digest/recall | **0 server errors** | Full benchmark pass |
| Cached recall latency (server) | p95 &lt; 100 ms | **p95 41 ms** | In-process metrics |
| Cached recall latency (end-to-end, c=20) | p95 &lt; 500 ms | **p95 159 ms** | Includes network RTT |
| Mixed workload (80% read / 20% write) | 0 errors @ **c=20** | **PASS** (500 req) | Practical concurrency per node |
| Digest backpressure | 429 when saturated, no silent drop | **PASS** | `rate_limited` tracked |
| Replay determinism | Byte-identical replays after first render | **24/24 PASS** | Cross-container |
| Cache hit rate (warm workload) | &gt; 95% | **99.57%** | 30 Gemini / 2,563 recalls |

**Explicitly out of scope for v0.2 reference SLO:**

- 50+ concurrent clients on one node without scale-out
- Hosted SaaS uptime (self-hosted — customer operates infra)
- First-render token determinism from shared LLM APIs

See [CAPACITY.md](CAPACITY.md) for tuning and [SCALING.md](SCALING.md) for read replicas.

---

## Standard tier

- Email support, business hours
- Security patches within 30 days
- Major releases quarterly

## Enterprise tier

- **24×7 P1** for production outage — see [SUPPORT.md](SUPPORT.md) for escalation path
- Indemnification & custom SLA (negotiated)
- Professional services: integration, entity ontologies, compliance mapping
- SOC 2 Type I alignment — see [SOC2_ROADMAP.md](SOC2_ROADMAP.md) (attestation in progress)

## Uptime

Self-hosted: uptime is **your** deployment SLO. We provide health/metrics/dashboard endpoints and the capacity guide; you operate Kubernetes/ACI behind your load balancer.

**Sizing rule of thumb (from Azure bench):** plan **~20 concurrent memory clients per 4 vCPU node** for mixed workloads; scale horizontally (see SCALING.md) beyond that.

Contact: Insight IT Solutions LLC — see README.
