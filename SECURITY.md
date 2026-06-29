# Security posture

Honest account of what's hardened and what still needs work before an enterprise sign-off.

## Hardened
- **Authentication.** All endpoints except `/health` require an API key
  (`PRISMCORTEX_API_KEY`, via `X-API-Key` or `Bearer`, constant-time compare). The server
  warns loudly if no key is set. Memory cannot be read, written, or erased unauthenticated.
- **Input limits.** Digest/recall payloads are size-capped (Pydantic `max_length`).
- **Secrets.** Keys come from a gitignored `.env`; verified no secret is in any tracked
  file. No secret is logged.
- **License integrity.** Ed25519 (asymmetric) — a client verifies but cannot forge keys.
  Offline, no phone-home (works air-gapped).
- **Erasure.** `/forget` hard-deletes a source's facts *and* clears the answer cache, so
  deleted content cannot linger; only an audit tombstone remains.
- **No `eval`/`exec`/`pickle`** of untrusted input; no shell-out on request paths.

## Deploy guidance (operator responsibility)
- **TLS:** terminate at a reverse proxy (nginx/Caddy/Azure App Gateway). The app speaks
  plain HTTP behind it.
- **Network:** keep the memory service on a private network; expose only the proxy.
- **Rotate** `PRISMCORTEX_API_KEY`; use a distinct key per client where possible.
- **Pin the model:** set `PRISMCORTEX_MODEL` to a *dated* Gemini snapshot — a floating
  alias silently changes outputs (the determinism guarantee is scoped to a pinned model).
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
- **Multi-tenant isolation.** The current store is single-tenant; tenant isolation is
  the caller's responsibility until per-tenant namespacing lands.
- **Dependency audit / SBOM.** Run `pip-audit` and pin transitive deps for a release.

Report vulnerabilities privately to the maintainer; do not open public issues for them.
