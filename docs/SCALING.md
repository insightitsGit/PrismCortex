# Horizontal scaling (read path)

## Today (v0.2)

- One process = one authoritative in-memory graph + durable PrismLib cache per tenant.
- Cached recalls are cheap (~1–20 ms); graph retrieval is in-process.

## Near-term pattern

1. **Write leader** — single container accepts `/digest` and `/sleep`.
2. **Read replicas** — N containers with shared cache DB (read-only SQLite or replicated PrismLib).
3. **Invalidation** — Chorus / mesh broadcasts version bumps (commercial tier); replicas drop hot cache entries on version change.

## 50k+ facts

Enable IVF ANN (`PRISMCORTEX_USE_ANN=1`, threshold 5000). For 500k+, swap to PrismRAG production adapter (ANN + governed retrieval).

## Multi-region

Pin `PRISMCORTEX_REGION` per deployment; tenant data under `tenants/{region}/{tenant_id}/`. No cross-region graph merge in v0.2.
