"""PrismCortex — deterministic, auditable, self-consolidating memory for AI agents.

    from prismcortex import reference_memory
    mem = reference_memory()                      # reference adapters + real Gemini
    mem.digest("My deploy budget is $40k.")
    mem.recall("What's my deploy budget?").answer

Swap the reference adapters for the real Insight ITS packages (prismlang, prismrag,
prismresonance, prismlib, Chorus) one port at a time — the engine never changes.
"""
from .engine import Memory
from .factory import reference_memory
from .models import (
    Band,
    DigestOutcome,
    DigestResult,
    Edge,
    GraphVersion,
    Node,
    RecallResult,
    StateDelta,
    Subgraph,
)

__version__ = "0.1.0"

__all__ = [
    "Memory",
    "reference_memory",
    "Band",
    "DigestOutcome",
    "DigestResult",
    "RecallResult",
    "Node",
    "Edge",
    "Subgraph",
    "StateDelta",
    "GraphVersion",
    "__version__",
]
