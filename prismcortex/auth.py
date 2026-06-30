"""API-key authentication with tenant scoping and RBAC.

Single-key mode (dev): ``PRISMCORTEX_API_KEY`` → tenant ``default``, all roles.

Multi-key mode (enterprise): ``PRISMCORTEX_API_KEYS`` JSON map::

    {"keyhex": {"tenant": "acme", "roles": ["read", "write", "admin"]}}

Or a path via ``PRISMCORTEX_API_KEYS_FILE``.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional

ROLE_READ = "read"
ROLE_WRITE = "write"
ROLE_ADMIN = "admin"
ROLE_FORGET = "forget"
ALL_ROLES = frozenset({ROLE_READ, ROLE_WRITE, ROLE_ADMIN, ROLE_FORGET})


@dataclass(frozen=True)
class AuthContext:
    tenant_id: str = "default"
    roles: frozenset[str] = field(default_factory=lambda: ALL_ROLES)
    region: str = "default"

    def allows(self, *required: str) -> bool:
        if ROLE_ADMIN in self.roles:
            return True
        return any(r in self.roles for r in required)


def _load_key_map() -> dict[str, dict]:
    raw = os.environ.get("PRISMCORTEX_API_KEYS")
    path = os.environ.get("PRISMCORTEX_API_KEYS_FILE")
    if path and os.path.isfile(path):
        raw = open(path, encoding="utf-8").read()
    if raw:
        return json.loads(raw)
    single = os.environ.get("PRISMCORTEX_API_KEY")
    if single:
        return {single: {"tenant": os.environ.get("PRISMCORTEX_TENANT", "default"), "roles": list(ALL_ROLES)}}
    return {}


_KEY_MAP: Optional[dict[str, dict]] = None


def key_map() -> dict[str, dict]:
    global _KEY_MAP
    if _KEY_MAP is None:
        _KEY_MAP = _load_key_map()
    return _KEY_MAP


def reload_keys() -> None:
    global _KEY_MAP
    _KEY_MAP = None


def authenticate(token: Optional[str]) -> Optional[AuthContext]:
    if not token:
        return None
    entry = key_map().get(token)
    if entry is None:
        return None
    roles = frozenset(entry.get("roles") or [ROLE_READ, ROLE_WRITE])
    region = entry.get("region") or os.environ.get("PRISMCORTEX_REGION", "default")
    return AuthContext(
        tenant_id=str(entry.get("tenant") or "default"),
        roles=roles | ({ROLE_ADMIN} if ROLE_ADMIN in roles else frozenset()),
        region=region,
    )


def auth_required() -> bool:
    return bool(key_map())
