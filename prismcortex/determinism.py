"""Content-addressing — the mechanism that makes the system deterministic.

The cache key is a hash of *the exact context that produced the answer*. Because the
key IS the content, a changed fact yields a changed key, so a stale answer is simply
unreachable — invalidation and determinism are the same mechanism. Timestamps are
deliberately excluded: the key depends on the current *knowledge*, not on when it was
recorded, so re-deriving identical facts hits the same answer.
"""
from __future__ import annotations

import hashlib
import json

from .models import Subgraph

_SEP = "\x00"


def canonical_subgraph(subgraph: Subgraph) -> str:
    """Stable serialization of the *current* knowledge in a subgraph.

    Sorted by id / (src, dst, relation) with explicit tie-breaks so ordering from the
    retrieval layer can never change the key. Validity timestamps are omitted on
    purpose (see module docstring).
    """
    nodes = sorted(
        (
            {
                "id": n.id,
                "label": n.label,
                "kind": n.kind,
                "attributes": _canonical_attrs(n.attributes),
            }
            for n in subgraph.nodes
        ),
        key=lambda x: x["id"],
    )
    edges = sorted(
        (
            {"src": e.src, "dst": e.dst, "relation": e.relation}
            for e in subgraph.edges
            if e.is_current
        ),
        key=lambda x: (x["src"], x["dst"], x["relation"]),
    )
    return json.dumps({"nodes": nodes, "edges": edges}, sort_keys=True, separators=(",", ":"))


def _canonical_attrs(attrs: dict) -> dict:
    # Only stable, JSON-serializable scalar attributes contribute to the address.
    return {k: attrs[k] for k in sorted(attrs) if isinstance(attrs[k], (str, int, float, bool))}


def content_address(query: str, subgraph: Subgraph, template_id: str, model_id: str) -> str:
    """The cache key. Pins to a model snapshot — a model rev correctly re-renders."""
    payload = _SEP.join(
        [
            " ".join(query.lower().split()),  # normalize whitespace/case
            canonical_subgraph(subgraph),
            template_id,
            model_id,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def extraction_memo_key(text: str, extractor_model_id: str) -> str:
    """Write-path memo key: re-digesting identical input is idempotent + reproducible."""
    payload = _SEP.join(["extract", " ".join(text.lower().split()), extractor_model_id])
    return "memo:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def graph_content_hash(serialized_current_edges: str) -> str:
    """Integrity stamp stored on GraphVersion (independent of the monotonic counter)."""
    return hashlib.sha256(serialized_current_edges.encode("utf-8")).hexdigest()
