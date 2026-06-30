"""Retention and legal-hold policy engine (GDPR + enterprise governance)."""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


class PolicyEngine:
    """Tracks legal holds and default retention; persists to PRISMCORTEX_DATA."""

    def __init__(self, data_dir: str, *, default_retention_days: int = 90) -> None:
        self._path = Path(data_dir) / "policy.json"
        self._lock = threading.Lock()
        self._default_days = int(os.environ.get("PRISMCORTEX_RETENTION_DAYS", default_retention_days))
        self._legal_holds: set[str] = set()
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._legal_holds = set(data.get("legal_holds", []))
            self._default_days = int(data.get("default_retention_days", self._default_days))

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps({
            "legal_holds": sorted(self._legal_holds),
            "default_retention_days": self._default_days,
        }, indent=2), encoding="utf-8")

    def add_legal_hold(self, source_id: str) -> None:
        with self._lock:
            self._legal_holds.add(source_id)
            self._save()

    def remove_legal_hold(self, source_id: str) -> None:
        with self._lock:
            self._legal_holds.discard(source_id)
            self._save()

    def legal_holds(self) -> list[str]:
        with self._lock:
            return sorted(self._legal_holds)

    def can_forget(self, source_id: str) -> tuple[bool, str]:
        with self._lock:
            if source_id in self._legal_holds:
                return False, "source under legal hold"
        return True, ""

    def retention_cutoff(self) -> datetime:
        return datetime.now(timezone.utc) - timedelta(days=self._default_days)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "default_retention_days": self._default_days,
                "legal_holds": sorted(self._legal_holds),
                "retention_cutoff": self.retention_cutoff().isoformat(),
            }
