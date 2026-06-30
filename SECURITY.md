# Security posture

Honest account of what's hardened and what still needs work before an enterprise sign-off.

## Hardened
- **Authentication.** Scoped API keys via `PRISMCORTEX_API_KEY` (single tenant) or
  `PRISMCORTEX_API_KEYS` / `_FILE` JSON (multi-tenant RBAC: read / write / forget / admin).
  Constant-time compare; `/health` and `/console` open.
- **Multi-tenant isolation.** Separate graph + PrismLib cache per tenant/region under
  `$PRISMCORTEX_DATA/tenants/{region}/{tenant_id}/`.
- **Rate limiting.** Optional `PRISMCORTEX_RATE_LIMIT_RPM` (per key, in-process).
- **Write backpressure.** `PRISMCORTEX_MAX_CONCURRENT_DIGEST` — returns 429 when saturated.
- **Prompt-injection mitigation.** User payloads wrapped in delimiters; basic sanitization
  before Gemini extraction/render.
- **Input limits.** Digest/recall payloads are size-capped (Pydantic `max_length`).
- **Secrets.** Keys come from a gitignored `.env`; verified no secret is in any tracked
  file. No secret is logged.
- **License integrity.** Ed25519 (asymmetric) — a client verifies but cannot forge keys.
  Offline, no phone-home (works air-gapped).
- **Erasure.** `/forget` hard-deletes a source's facts *and* clears the answer cache, so
  deleted content cannot linger; only an audit tombstone remains.
- **No `eval`/`exec`/`pickle`** of untrusted input; no shell-out on request paths.
- **Dependency audit.** `pip-audit` on PrismCortex's own dependency tree (pydantic, numpy,
  cryptography, google-genai, fastapi, uvicorn, freshly resolved): **no known
  vulnerabilities**. The image installs into a clean slim base, so that's what ships.
  (Re-run `pip-audit -r` per release; audit your global env separately — unrelated tools
  there will show CVEs that don't ship with PrismCortex.)

## Deploy guidance (operator responsibility)
- **TLS:** terminate at a reverse proxy (nginx/Caddy/Azure App Gateway). The app speaks
  plain HTTP behind it.
- **Network:** keep the memory service on a private network; expose only the proxy.
- **Rotate** `PRISMCORTEX_API_KEY`; use a distinct key per client where possible.
- **Pin the model:** dated `gemini-2.5-flash-NNN` snapshots aren't exposed for all keys,
  so the practical pin is an **`@epoch`**: set `PRISMCORTEX_MODEL=gemini-2.5-flash@2026-06`.
  The epoch is part of the cache key (bump it after a known model change to invalidate
  frozen answers) but is stripped for the API call. A bare alias logs a warning.
- **Replace the demo license public key** in `licensing.py` with your own keypair
  (`generate_keypair()`); keep the private key offline.

## Known gaps — required before an enterprise security sign-off
- **Professional pen-test / audit.** This is automated + manual self-review, not a
  third-party audit. Get one before signing a regulated customer.
- **Rate limiting / abuse controls.** Not built in — add at the proxy.
- **Prompt-injection surface.** User content flows into the extraction/render prompts.
  The renderer is constrained (extractive + verification), but a determined injection
  could influence extraction. Treat ingested content as untrusted; don't auto-execute
  anything derived from memory.
- **Multi-tenant isolation.** Per-tenant stores; cross-tenant reads impossible by construction.
  RBAC scopes write/forget/admin operations.
- **SBOM + pinned transitive deps** for a reproducible release (core tree audits clean today).

Report vulnerabilities privately to the maintainer; do not open public issues for them.
