"""Convenience builders that wire a ready-to-run Memory."""
from __future__ import annotations

from typing import Optional

from .adapters.reference import (
    DurableCache,
    HashingProjector,
    InMemoryGraphStore,
    InProcessMesh,
    InProcessResonance,
    ListStaging,
)
from .engine import Memory


def reference_memory(
    *,
    model: Optional[str] = None,
    cache_path: Optional[str] = None,
    embedding_dim: int = 384,
    k: int = 8,
    max_facts: Optional[int] = None,
    llm=None,
) -> Memory:
    """A fully wired Memory: reference adapters + the real Gemini client.

    Needs `google-genai` and GEMINI_API_KEY / GOOGLE_API_KEY (extraction & rendering
    are real Gemini calls). The Gemini import is lazy so the rest of the package stays
    importable without it. Pass ``llm`` to inject a custom extractor/renderer (e.g. a
    call-counting wrapper for benchmarks).
    """
    if llm is None:
        from .llm.gemini import GeminiClient

        llm = GeminiClient(model=model)
    return Memory(
        projector=HashingProjector(dim=embedding_dim),
        extractor=llm,
        renderer=llm,
        store=InMemoryGraphStore(),
        resonance=InProcessResonance(),
        cache=DurableCache(path=cache_path),
        mesh=InProcessMesh(),
        staging=ListStaging(),
        k=k,
        max_facts=max_facts,
    )
