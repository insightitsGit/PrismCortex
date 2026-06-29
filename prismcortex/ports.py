"""Port interfaces — the seams where the five Insight ITS packages plug in.

PrismCortex never imports a Prism package directly; it talks to these Protocols. The
reference adapters (``adapters/reference.py``) implement them with real in-memory logic
so the engine runs and tests today; the production adapters wrap the real packages and
are swapped in one line at a time.
"""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from .models import (
    AssetPointer,
    ExtractedGist,
    GraphVersion,
    StateDelta,
    Subgraph,
)


@runtime_checkable
class GistProjector(Protocol):
    """PrismLang — deterministic projection of text into a vector + taxonomy.

    Must be CPU-stable: the same text always yields the same vector, or the read-path
    determinism contract breaks.
    """

    def embed(self, text: str) -> list[float]: ...
    def classify(self, text: str) -> str: ...


@runtime_checkable
class EntityExtractor(Protocol):
    """LLM (Gemini) — turns a payload + local context into a structured gist.

    This is the stochastic *write* path; its output is memoized on input hash so
    re-digesting identical text is reproducible.
    """

    def extract(self, text: str, context: Subgraph) -> ExtractedGist: ...


@runtime_checkable
class Renderer(Protocol):
    """LLM (Gemini) — paints a subgraph into prose. Facts are substituted from the
    graph (extractive); only connective wording is generated. Called at most once per
    content address (then frozen in the cache)."""

    def render(self, query: str, subgraph: Subgraph) -> str: ...

    @property
    def model_id(self) -> str: ...


@runtime_checkable
class GraphStore(Protocol):
    """PrismRAG — the bitemporal engram (source of truth)."""

    def retrieve(self, embedding: list[float], k: int = 8) -> Subgraph: ...
    def find_node_by_label(self, label: str) -> Optional[str]: ...
    def find_similar_node(self, embedding: list[float], threshold: float = 0.88) -> Optional[str]: ...
    def current_edge(self, src: str, relation: str) -> Optional[str]: ...
    def apply(self, delta: StateDelta) -> GraphVersion: ...
    def version(self) -> GraphVersion: ...


@runtime_checkable
class ResonanceEngine(Protocol):
    """PrismResonance — synaptic weights, salience, and discrete consolidation.

    Weights are frozen between ``consolidate()`` (sleep) passes so a fixed version is
    reproducible.
    """

    def ingest(self, chunk_id: str, amplitude: list[float], band: str) -> None: ...
    def reinforce(self, chunk_id: str) -> None: ...
    def rank(self, candidate_ids: list[str]) -> list[str]: ...
    def consolidate(self) -> None: ...


@runtime_checkable
class ResponseCache(Protocol):
    """PrismLib cache-as-failover — durable, content-addressed store for rendered
    answers and write-path memos. Not volatile: persistence is what makes a frozen
    answer stable across restarts and cache loss."""

    def get(self, key: str) -> Optional[str]: ...
    def put(self, key: str, value: str) -> None: ...
    def has(self, key: str) -> bool: ...


@runtime_checkable
class MeshBroadcast(Protocol):
    """Chorus / PrismLib cluster — broadcasts version bumps and cache invalidations
    across agents. Carries *notifications*, never writes (single source of truth)."""

    def broadcast_version(self, version: GraphVersion, invalidated: list[str]) -> None: ...


@runtime_checkable
class StagingBuffer(Protocol):
    """The labile working-memory store. Holds uncertain deltas until sleep() resolves
    them. Outside the deterministic recall path by default."""

    def stage(self, delta: StateDelta, reason: str) -> None: ...
    def drain(self) -> list[tuple[StateDelta, str]]: ...
    def pending_count(self) -> int: ...


@runtime_checkable
class BlobStore(Protocol):
    """Immutable object storage for raw multi-modal assets."""

    def put(self, data: bytes, modality: str, uri_hint: str = "") -> AssetPointer: ...
    def get(self, asset_id: str) -> bytes: ...
