"""Open-core licensing gate — offline, asymmetric (Ed25519), no phone-home.

The OSS core never calls this. Commercial modules call ``require_license()`` at import.
Keys are signed with a PRIVATE key held offline by the issuer and verified locally with
the EMBEDDED PUBLIC key — so a client can verify but cannot forge (unlike a symmetric
HMAC), and it works fully air-gapped. Mirrors the pattern in prismrag-patch.

Key format:  base64url(payload_json) + '.' + base64url(ed25519_signature)
payload_json = {"tier","expiry","customer","features"}
"""
from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


class LicenseError(RuntimeError):
    pass


class LicenseExpiredError(LicenseError):
    pass


# Public verify key (hex). The matching PRIVATE key is held OFFLINE by the issuer and is
# never in this repo. Replace with your own (see generate_keypair) or override at runtime
# via PRISMCORTEX_LICENSE_PUBKEY.
_DEFAULT_PUBKEY_HEX = "902263c299058a70114d04cf9e02916cd28e6e1c4865bd96e9716dae4e2204d3"


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _public_key() -> Ed25519PublicKey:
    hexkey = os.environ.get("PRISMCORTEX_LICENSE_PUBKEY", _DEFAULT_PUBKEY_HEX)
    return Ed25519PublicKey.from_public_bytes(bytes.fromhex(hexkey))


def verify_license(key: Optional[str] = None) -> dict:
    key = key or os.environ.get("PRISMCORTEX_LICENSE_KEY")
    if not key:
        raise LicenseError("No license key. Set PRISMCORTEX_LICENSE_KEY for commercial modules.")
    try:
        body_b64, sig_b64 = key.strip().split(".", 1)
        body, sig = _b64d(body_b64), _b64d(sig_b64)
    except Exception as exc:  # noqa: BLE001
        raise LicenseError("Malformed license key.") from exc

    try:
        _public_key().verify(sig, body)  # raises if forged/tampered
    except InvalidSignature as exc:
        raise LicenseError("Invalid license signature.") from exc

    info = json.loads(body.decode())
    if datetime.now(timezone.utc) > datetime.fromisoformat(info["expiry"]):
        raise LicenseExpiredError(f"License expired on {info['expiry']}.")
    return info


def require_license(min_tier: str = "pro") -> dict:
    return verify_license()


# --- issuer-side helpers (run where the PRIVATE key lives — never inside the client) ---

def issue_key(private_key_hex: str, tier: str, expiry_iso: str, customer: str,
              features: Optional[list] = None) -> str:
    sk = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
    body = json.dumps(
        {"tier": tier, "expiry": expiry_iso, "customer": customer, "features": features or []},
        separators=(",", ":"), sort_keys=True,
    ).encode()
    return _b64e(body) + "." + _b64e(sk.sign(body))


def generate_keypair() -> tuple[str, str]:
    """Run once for setup. Embed the PUBLIC hex in _DEFAULT_PUBKEY_HEX; keep PRIVATE offline."""
    sk = Ed25519PrivateKey.generate()
    priv = sk.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                            serialization.NoEncryption()).hex()
    pub = sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    return priv, pub
