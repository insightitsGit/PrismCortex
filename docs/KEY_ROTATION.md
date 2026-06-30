# License & API key rotation

## API keys

1. Generate new keys per tenant in `PRISMCORTEX_API_KEYS` JSON.
2. Deploy updated env or `PRISMCORTEX_API_KEYS_FILE`.
3. Call `auth.reload_keys()` or restart containers.
4. Revoke old keys from the map.

## Ed25519 license keys (commercial tier)

1. Run `python -c "from prismcortex.licensing import generate_keypair; print(generate_keypair())"` **offline**.
2. Replace `_DEFAULT_PUBKEY_HEX` in `licensing.py` or set `PRISMCORTEX_LICENSE_PUBKEY`.
3. Keep private key air-gapped; sign customer payloads with expiry + feature flags.

Never commit private keys.
