"""Core data models for PrismCortex.

Everything that crosses a port boundary is one of these. The graph is *bitemporal*:
edges carry validity intervals and are never destroyed — corrections invalidate the
old edge and add a new one, preserving provenance and enabling time-travel.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Band(str, enum.Enum):
    """Salience bands, mirroring prismresonance.FrequencyFamily.

    They route a payload between the fast (inline) and slow (staging→sleep) paths.
    """

    EMERGENCY = "EMERGENCY"  # flashbulb — fast-track commit even if uncertain
    ALERT = "ALERT"          # fast-track commit (corrections, urgent)
    NORMAL = "NORMAL"        # default
    RECOVERY = "RECOVERY"
    NEUTRAL = "NEUTRAL"      # low value — skip extraction (cost gate)
    ARCHIVE = "ARCHIVE"      # noise — skip


# Bands that bypass the staging buffer and consolidate immediately.
FAST_TRACK_BANDS = frozenset({Band.EMERGENCY, Band.ALERT})
# Bands cheap enough to skip the expensive extraction entirely.
SKIP_BANDS = frozenset({Band.NEUTRAL, Band.ARCHIVE})


class Operation(str, enum.Enum):
    ASSIMILATE = "assimilate"    # new node/edge grafted onto the graph
    ACCOMMODATE = "accommodate"  # invalidate an existing edge + add its replacement
    REINFORCE = "reinforce"      # raise weight of an existing node/edge (LTP)
    PRUNE = "prune"              # soft-invalidate (never destructive)


class Provenance(BaseModel):
    """Where a fact came from. Kept so every answer is traceable to its source."""

    source_id: str
    modality: str = "text"  # text | image | video | audio
    recorded_at: datetime = Field(default_factory=utcnow)
    raw_ref: Optional[str] = None  # pointer into cold storage (raw never in context)
    agent_id: Optional[str] = None


class Node(BaseModel):
    id: str
    label: str
    kind: str = "entity"
    embedding: Optional[list[float]] = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    weight: float = 1.0
    confidence: float = 1.0
    band: Band = Band.NORMAL
    created_at: datetime = Field(default_factory=utcnow)
    provenance: Optional[Provenance] = None


class Edge(BaseModel):
    id: str
    src: str  # Node.id
    dst: str  # Node.id
    relation: str
    weight: float = 1.0
    confidence: float = 1.0
    valid_from: datetime = Field(default_factory=utcnow)
    valid_to: Optional[datetime] = None  # None == currently true
    recorded_at: datetime = Field(default_factory=utcnow)
    band: Band = Band.NORMAL
    provenance: Optional[Provenance] = None

    @property
    def is_current(self) -> bool:
        return self.valid_to is None


class AssetSegment(BaseModel):
    """A timecoded slice of an immutable blob (scene / passage)."""

    t_start: float
    t_end: float
    description: str
    node_ids: list[str] = Field(default_factory=list)


class AssetPointer(BaseModel):
    """Immutable blob asset: raw stays in object storage, only the pointer + extracted
    descriptions enter the graph. You can't inject into the middle of an mp4 — so you
    don't try; you mutate the description nodes instead."""

    asset_id: str
    uri: str
    modality: str
    sha256: str
    segments: list[AssetSegment] = Field(default_factory=list)


class Subgraph(BaseModel):
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)


# --- extraction (what the LLM returns from a payload) ---------------------------

class ExtractedEntity(BaseModel):
    label: str
    kind: str = "entity"
    attributes: dict[str, Any] = Field(default_factory=dict)


class ExtractedRelation(BaseModel):
    src: str       # entity label (resolved to a Node.id during delta calculation)
    dst: str
    relation: str


class ExtractedGist(BaseModel):
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relations: list[ExtractedRelation] = Field(default_factory=list)
    is_correction: bool = False  # signals an ACCOMMODATE rather than ASSIMILATE
    notes: str = ""


# --- deltas (the mutation applied to the graph) ---------------------------------

class DeltaOp(BaseModel):
    operation: Operation
    node: Optional[Node] = None
    edge: Optional[Edge] = None
    target_id: Optional[str] = None  # existing node/edge id for REINFORCE/PRUNE/ACCOMMODATE
    reason: str = ""


class StateDelta(BaseModel):
    ops: list[DeltaOp] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.ops


class GraphVersion(BaseModel):
    """Monotonic counter + content hash. Bumped at every commit (inline or sleep)."""

    version: int = 0
    content_hash: str = ""
    updated_at: datetime = Field(default_factory=utcnow)


# --- results --------------------------------------------------------------------

class DigestOutcome(str, enum.Enum):
    SKIPPED = "skipped"        # low salience or already-digested (idempotent)
    REINFORCED = "reinforced"  # only weight changes, no new topology
    COMMITTED = "committed"    # delta applied to the authoritative graph inline
    STAGED = "staged"          # parked in the labile buffer, awaits sleep()


class DigestResult(BaseModel):
    outcome: DigestOutcome
    band: Band
    delta: StateDelta = Field(default_factory=StateDelta)
    version: GraphVersion
    reason: str = ""


class RecallResult(BaseModel):
    answer: str
    cache_hit: bool
    subgraph_hash: str           # the content address that keys this answer
    version: int
    model_id: str
    node_ids: list[str] = Field(default_factory=list)
    edge_ids: list[str] = Field(default_factory=list)
    provisional: bool = False    # answer touched staged (unconsolidated) knowledge
