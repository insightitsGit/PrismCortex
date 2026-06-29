"""Production adapters — the real Insight ITS packages behind the ports.

Import-guarded so the OSS core stays installable without them (`pip install
prismcortex[prism]`). Each class wraps exactly one package:

  - PrismLangProjector  → prismlang.PrismProjector   (deterministic, CPU-stable vectors)
  - PrismResonanceAdapter → prismresonance.PrismResonance (wavepacket weight + sleep)
  - PrismLibCache       → prismlib SQLiteStore        (durable cache-as-failover)

The bitemporal GraphStore stays PrismCortex-owned (the reference store *is* the design
— prismrag-patch is a retrieval governor, not a bitemporal database, so it slots in as
a recall-time filter rather than the store itself). The Chorus/prismlib cluster mesh is
the remaining seam; InProcessMesh stands in until it's wired.
"""
from __future__ import annotations

import os
import time
from typing import Optional

import numpy as np


class PrismLangProjector:
    """GistProjector via prismlang.PrismProjector.

    project() returns (category_slug, vector, trace). The vector is all-MiniLM-L6-v2
    JL-reduced with a seed derived from tenant_id — deterministic given a fixed tenant,
    which is exactly the CPU-stable projection the read-path determinism contract needs.
    """

    def __init__(self, taxonomy=None, tenant_id: str = "prismcortex", k: int = 128) -> None:
        # k = projection dimension. PrismLang defaults to 64, which crowds at scale
        # (retrieval recall drops to ~0.86 at 3k facts); 128 restores it to ~0.97 with no
        # latency cost. See benchmarks/scale_bench.py.
        from prismlang import Category, PrismProjector, TaxonomyConfig

        if taxonomy is None:
            taxonomy = TaxonomyConfig(categories=[
                Category("general", "General", ["the", "a", "is", "of", "to"]),
                Category("preference", "Preference", ["like", "prefer", "favorite", "want", "hate"]),
                Category("fact", "Fact", ["is", "are", "has", "budget", "name", "id", "number"]),
                Category("tech", "Tech", ["deploy", "database", "server", "region", "api", "model"]),
            ])
        self._p = PrismProjector(taxonomy, tenant_id=tenant_id, k=k)
        _, probe, _ = self._p.project("dimension probe")
        self.dim = len(probe)

    def embed(self, text: str) -> list[float]:
        _, vec, _ = self._p.project(text)
        return [float(x) for x in vec]

    def classify(self, text: str) -> str:
        cat, _, _ = self._p.project(text)
        return cat


class PrismResonanceAdapter:
    """ResonanceEngine via prismresonance.PrismResonance (compiles an ONNX graph on
    first construction; writes a small state db)."""

    def __init__(self, embedding_dim: int, state_path: str = "resonance_state.db", onnx_path: str = "resonance_engine.onnx") -> None:
        from prismresonance import PrismResonance
        from prismresonance.frequency import FrequencyFamily

        self._FF = FrequencyFamily
        self._r = PrismResonance.create(embedding_dim=embedding_dim, state_path=state_path, onnx_path=onnx_path)
        self._amps: dict[str, np.ndarray] = {}  # kept so reinforce can re-ingest

    def _freq(self, band: str):
        return getattr(self._FF, band, self._FF.NEUTRAL)

    def ingest(self, chunk_id: str, amplitude: list[float], band: str) -> None:
        amp = np.asarray(amplitude, dtype=np.float32)
        if amp.size == 0:
            return
        self._amps[chunk_id] = amp
        self._r.ingest(chunk_id, amp, self._freq(band))

    def reinforce(self, chunk_id: str) -> None:
        amp = self._amps.get(chunk_id)
        if amp is not None:  # re-ingest at higher salience ≈ LTP
            self._r.ingest(chunk_id, amp, self._FF.ALERT)

    def rank(self, candidate_ids: list[str]) -> list[str]:
        return list(candidate_ids)  # resonance ordering is not on the determinism path

    def consolidate(self) -> None:
        self._r.sleep()

    def shutdown(self) -> None:
        try:
            self._r.shutdown()
        except Exception:
            pass


class PrismLibCache:
    """ResponseCache via prismlib SQLiteStore — exact-key, durable (cache-as-failover).

    packet_id carries our content-address; response carries the frozen answer. Durable
    by file path so a frozen answer survives restart and cache eviction.
    """

    _TEN_YEARS = 10 * 365 * 24 * 3600

    def __init__(self, db_path: str = ".prismcortex_cache/prismlib.db") -> None:
        from prism.cache import CacheEntry, SQLiteStore

        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._CacheEntry = CacheEntry
        self._db_path = db_path
        self._store = SQLiteStore(db_path=db_path)

    def get(self, key: str) -> Optional[str]:
        entry = self._store.load(key)
        return entry.response if entry else None

    def has(self, key: str) -> bool:
        return self._store.load(key) is not None

    def put(self, key: str, value: str) -> None:
        now = time.time()
        self._store.save(self._CacheEntry(
            packet_id=key, query_text="", response=value,
            created_at=now, expires_at=now + self._TEN_YEARS,
        ))

    def clear(self) -> None:
        """Drop all cached answers (recreate the store) — used on erasure."""
        from prism.cache import SQLiteStore

        try:
            self._store.close()
        except Exception:  # noqa: BLE001
            pass
        if self._db_path != ":memory:" and os.path.exists(self._db_path):
            os.remove(self._db_path)
        self._store = SQLiteStore(db_path=self._db_path)


def prism_memory(
    *,
    model: Optional[str] = None,
    cache_db: str = ".prismcortex_cache/prismlib.db",
    tenant_id: str = "prismcortex",
    resonance_state: str = ".prismcortex_cache/resonance_state.db",
    resonance_onnx: str = ".prismcortex_cache/resonance_engine.onnx",
    k: int = 8,
):
    """Production-wired Memory: real PrismLang + PrismResonance + PrismLib + Gemini.

    GraphStore + Mesh remain the reference (PrismCortex-owned bitemporal store; mesh is
    the open Chorus seam). Needs prismcortex[prism], prismcortex[gemini], and a key.
    """
    from ..engine import Memory
    from ..llm.gemini import GeminiClient
    from .reference import InMemoryGraphStore, InProcessMesh, ListStaging

    projector = PrismLangProjector(tenant_id=tenant_id)
    resonance = PrismResonanceAdapter(embedding_dim=projector.dim, state_path=resonance_state, onnx_path=resonance_onnx)
    cache = PrismLibCache(db_path=cache_db)
    gemini = GeminiClient(model=model)
    return Memory(
        projector=projector,
        extractor=gemini,
        renderer=gemini,
        store=InMemoryGraphStore(),
        resonance=resonance,
        cache=cache,
        mesh=InProcessMesh(),
        staging=ListStaging(),
        k=k,
    )
