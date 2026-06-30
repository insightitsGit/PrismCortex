# Operations runbook

## Model epoch governance

1. Pin `PRISMCORTEX_MODEL=gemini-2.5-flash@2026-06` (epoch in cache key).
2. After a known Google model change, bump epoch → all frozen answers invalidate.
3. Run `/reset` or redeploy to clear in-process state for benchmarks.

## On-call: wrong answer

1. `POST /explain` with the query → evidence trail.
2. `GET /replay_certificate?query=...` → content address + version.
3. `GET /dashboard` → cache hit rate, staging backlog, open conflicts.
4. Check structured logs (`server.jsonl`) for `trace_id` spans when `PRISMCORTEX_TRACE=1`.

## Alerts (health endpoint)

- `staging backlog > PRISMCORTEX_STAGING_WARN` → run `POST /sleep` or investigate extraction conflicts.
- `errors` count elevated → check Gemini quota / network.

## Tenant isolation

- Configure `PRISMCORTEX_API_KEYS` JSON with per-tenant keys.
- Data paths: `$PRISMCORTEX_DATA/tenants/{region}/{tenant_id}/`.

## Legal hold

- `POST /legal_hold {"source_id": "..."}` blocks `/forget` until `DELETE /legal_hold/{source_id}`.
