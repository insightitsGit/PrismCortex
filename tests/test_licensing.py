"""Ed25519 license gate — a client can verify but cannot forge, tamper, or replay."""
from datetime import datetime, timedelta, timezone

import pytest

from prismcortex import licensing


def _exp(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def test_valid_license_verifies(monkeypatch):
    priv, pub = licensing.generate_keypair()
    monkeypatch.setenv("PRISMCORTEX_LICENSE_PUBKEY", pub)
    key = licensing.issue_key(priv, "pro", _exp(30), "Acme Corp", features=["audit"])
    info = licensing.verify_license(key)
    assert info["tier"] == "pro" and info["customer"] == "Acme Corp" and "audit" in info["features"]


def test_tampered_signature_rejected(monkeypatch):
    priv, pub = licensing.generate_keypair()
    monkeypatch.setenv("PRISMCORTEX_LICENSE_PUBKEY", pub)
    key = licensing.issue_key(priv, "pro", _exp(30), "Acme")
    body, sig = key.split(".", 1)
    tampered = body + "." + ("A" if sig[0] != "A" else "B") + sig[1:]
    with pytest.raises(licensing.LicenseError):
        licensing.verify_license(tampered)


def test_expired_license_rejected(monkeypatch):
    priv, pub = licensing.generate_keypair()
    monkeypatch.setenv("PRISMCORTEX_LICENSE_PUBKEY", pub)
    expired = licensing.issue_key(priv, "pro", _exp(-1), "Acme")
    with pytest.raises(licensing.LicenseExpiredError):
        licensing.verify_license(expired)


def test_forged_with_other_key_rejected(monkeypatch):
    _, pub = licensing.generate_keypair()          # the trusted public key
    other_priv, _ = licensing.generate_keypair()   # an attacker's key
    monkeypatch.setenv("PRISMCORTEX_LICENSE_PUBKEY", pub)
    forged = licensing.issue_key(other_priv, "enterprise", _exp(3650), "Attacker")
    with pytest.raises(licensing.LicenseError):
        licensing.verify_license(forged)
