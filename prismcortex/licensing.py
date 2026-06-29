"""Open-core licensing gate (offline, no phone-home).

The OSS core never calls this. Commercial modules call `require_license()` at import.
Keys are signed + time-bound and verified locally, so they work in air-gapped /
regulated deployments. This reference uses HMAC for simplicity; production should sign
with an asymmetric key (Ed25519) so the verifying public key can ship in the client
without exposing the signing secret. Mirrors the pattern already in prismrag-patch.

Key format:  base64( '<tier>|<expiry-iso>|<customer>' ) + '.' + hex(signature)
"""
from __future__ import annotations

import base64
import hmac
import os
from datetime import datetime, timezone
from hashlib import sha256
from typing import Optional


class LicenseError(RuntimeError):
    pass


class LicenseExpiredError(LicenseError):
    pass


# Demo verification secret. Production replaces with an Ed25519 public key check.
_PUBLIC_VERIFY_SECRET = os.environ.get("PRISMCORTEX_LICENSE_SECRET", "prismcortex-demo-verify").encode()


def verify_license(key: Optional[str] = None) -> dict:
    key = key or os.environ.get("PRISMCORTEX_LICENSE_KEY")
    if not key:
        raise LicenseError("No license key. Set PRISMCORTEX_LICENSE_KEY for commercial modules.")
    try:
        body_b64, sig = key.strip().split(".", 1)
        body = base64.urlsafe_b64decode(body_b64.encode()).decode()
        tier, expiry, customer = body.split("|", 2)
    except Exception as exc:
        raise LicenseError("Malformed license key.") from exc

    expected = hmac.new(_PUBLIC_VERIFY_SECRET, body.encode(), sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise LicenseError("Invalid license signature.")
    if datetime.now(timezone.utc) > datetime.fromisoformat(expiry):
        raise LicenseExpiredError(f"License expired on {expiry}.")
    return {"tier": tier, "expiry": expiry, "customer": customer}


def require_license(min_tier: str = "pro") -> dict:
    info = verify_license()
    return info


def issue_demo_key(tier: str, expiry_iso: str, customer: str) -> str:
    """Helper to mint a demo key for testing the gate (not for production issuance)."""
    body = f"{tier}|{expiry_iso}|{customer}"
    sig = hmac.new(_PUBLIC_VERIFY_SECRET, body.encode(), sha256).hexdigest()
    return base64.urlsafe_b64encode(body.encode()).decode() + "." + sig
