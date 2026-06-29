"""Reference adapters — real, in-memory implementations of every port.

These are NOT mocks: the embeddings use the hashing trick (deterministic, no
randomness), the graph is a genuine bitemporal store, the cache is content-addressed
and optionally durable, and resonance applies real weight/decay. They make the engine
run and test today; the production adapters wrap the real Prism packages behind the
same ports.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Optional

import numpy as np

from ..determinism import graph_content_hash
from ..models import (
    AssetPointer,
    Band,
    DeltaOp,
    Edge,
    GraphVersion,
    Node,
    Operation,
    StateDelta,
    Subgraph,
    utcnow,
)

_WORD = re.compile(r"[a-z0-9]+")


def _stable_hash_int(token: str, nbytes: int = 4) -> int:
    # hashlib (not builtin hash, which is per-process salted) → cross-run deterministic.
    return int.from_bytes(hashlib.blake2b(token.encode(), digest_size=nbytes).digest(), "big")


# --------------------------------------------------------------------------- #
# PrismLang stand-in: deterministic feature-hashing projector.
# --------------------------------------------------------------------------- #
class HashingProjector:
    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        v = np.zeros(self.dim, dtype=np.float32)
        for tok in _WORD.findall(text.lower()):
            d = hashlib.blake2b(tok.encode(), digest_size=8).digest()
            idx = int.from_bytes(d[:4], "big") % self.dim
            v[idx] += 1.0 if (d[4] & 1) else -1.0
        n = float(np.linalg.norm(v))
        return (v / n).tolist() if n > 0 else v.tolist()

    def classify(self, text: str) -> str:
        return "general"


# --------------------------------------------------------------------------- #
# PrismRAG stand-in: bitemporal in-memory graph store.
# --------------------------------------------------------------------------- #
class InMemoryGraphStore:
    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._edges: dict[str, Edge] = {}
        self._label_index: dict[str, str] = {}  # lower(label) -> node_id
        self._version = 0
        # cached unit-normalized embedding matrix for vectorized retrieval (rebuilt lazily)
        self._emb_ids: list[str] = []
        self._emb_unit = None  # np.ndarray [n_nodes, dim]
        self._matrix_dirty = True

    def _ensure_matrix(self) -> None:
        if not self._matrix_dirty:
            return
        ids, vecs = [], []
        for nid, node in self._nodes.items():
            if node.embedding:
                ids.append(nid)
                vecs.append(node.embedding)
        self._emb_ids = ids
        if vecs:
            m = np.asarray(vecs, dtype=np.float32)
            norms = np.linalg.norm(m, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self._emb_unit = m / norms
        else:
            self._emb_unit = None
        self._matrix_dirty = False

    # -- reads --
    def find_node_by_label(self, label: str) -> Optional[str]:
        return self._label_index.get(label.strip().lower())

    def current_edge(self, src: str, relation: str) -> Optional[Edge]:
        for e in self._edges.values():
            if e.is_current and e.src == src and e.relation == relation:
                return e
        return None

    def find_similar_node(self, embedding: list[float], threshold: float = 0.88) -> Optional[str]:
        """Entity resolution: the existing node whose embedding is closest to `embedding`,
        if above `threshold`. Lets a paraphrased subject ("the budget" vs "deploy budget")
        resolve to the same node without relying on the LLM to canonicalize perfectly."""
        if not embedding:
            return None
        self._ensure_matrix()
        if self._emb_unit is None:
            return None
        q = np.asarray(embedding, dtype=np.float32)
        qn = float(np.linalg.norm(q)) or 1.0
        sims = self._emb_unit @ (q / qn)  # rows are unit-normalized → cosine
        i = int(np.argmax(sims))
        return self._emb_ids[i] if float(sims[i]) >= threshold else None

    def retrieve(self, embedding: list[float], k: int = 8) -> Subgraph:
        if not self._nodes:
            return Subgraph()
        self._ensure_matrix()
        if self._emb_unit is None:
            return Subgraph()
        q = np.asarray(embedding, dtype=np.float32)
        qn = float(np.linalg.norm(q)) or 1.0
        sims = self._emb_unit @ (q / qn)
        kk = min(k, len(self._emb_ids))
        # stable top-k → deterministic retrieval set (subgraph is canonically sorted in the key)
        order = np.argsort(-sims, kind="stable")[:kk]
        chosen = {self._emb_ids[int(i)] for i in order}

        edges = [e for e in self._edges.values() if e.is_current and (e.src in chosen or e.dst in chosen)]
        # pull in neighbor nodes so the subgraph is self-contained and renderable.
        for e in edges:
            chosen.add(e.src)
            chosen.add(e.dst)
        nodes = [self._nodes[n] for n in chosen if n in self._nodes]
        return Subgraph(nodes=nodes, edges=edges)

    def version(self) -> GraphVersion:
        return GraphVersion(version=self._version, content_hash=self._content_hash())

    # -- write (the only mutation entry point) --
    def apply(self, delta: StateDelta) -> GraphVersion:
        if delta.is_empty:
            return self.version()
        now = utcnow()
        for op in delta.ops:
            if op.operation is Operation.ASSIMILATE:
                if op.node is not None:
                    self._nodes[op.node.id] = op.node
                    self._label_index[op.node.label.strip().lower()] = op.node.id
                    self._matrix_dirty = True  # invalidate the cached embedding matrix
                if op.edge is not None:
                    self._edges[op.edge.id] = op.edge
            elif op.operation is Operation.ACCOMMODATE:
                if op.target_id and op.target_id in self._edges:
                    self._edges[op.target_id].valid_to = now  # invalidate, never delete
                if op.edge is not None:
                    self._edges[op.edge.id] = op.edge
            elif op.operation is Operation.REINFORCE:
                self._reinforce(op.target_id)
            elif op.operation is Operation.PRUNE:
                if op.target_id and op.target_id in self._edges:
                    self._edges[op.target_id].valid_to = now
        self._version += 1
        return self.version()

    def prune_to(self, max_current_edges: int) -> int:
        """Bound the active working set: soft-invalidate the coldest (lowest-weight, then
        oldest) current edges until at most `max_current_edges` remain. Invalidated facts
        are retained (valid_to set) for audit/time-travel, just out of the recall path."""
        current = [e for e in self._edges.values() if e.is_current]
        if len(current) <= max_current_edges:
            return 0
        now = utcnow()
        current.sort(key=lambda e: (e.weight, e.recorded_at))  # coldest first
        for e in current[: len(current) - max_current_edges]:
            e.valid_to = now
        return len(current) - max_current_edges

    def _reinforce(self, target_id: Optional[str]) -> None:
        if not target_id:
            return
        if target_id in self._nodes:
            self._nodes[target_id].weight = min(self._nodes[target_id].weight + 0.5, 100.0)
        elif target_id in self._edges:
            self._edges[target_id].weight = min(self._edges[target_id].weight + 0.5, 100.0)

    def _content_hash(self) -> str:
        current = sorted(
            f"{e.src}|{e.relation}|{e.dst}" for e in self._edges.values() if e.is_current
        )
        return graph_content_hash(json.dumps(current, separators=(",", ":")))

    # -- introspection helpers (used by the audit/time-travel + memory-savings demo) --
    def history(self, src: str, relation: str) -> list[Edge]:
        return [e for e in self._edges.values() if e.src == src and e.relation == relation]

    def all_edges(self) -> list[Edge]:
        return list(self._edges.values())

    def all_nodes(self) -> list[Node]:
        return list(self._nodes.values())


# --------------------------------------------------------------------------- #
# PrismResonance stand-in: synaptic weight + discrete consolidation.
# --------------------------------------------------------------------------- #
_BAND_AMP = {
    Band.EMERGENCY.value: 4.0,
    Band.ALERT.value: 3.0,
    Band.NORMAL.value: 1.0,
    Band.RECOVERY.value: 1.0,
    Band.NEUTRAL.value: 0.5,
    Band.ARCHIVE.value: 0.25,
}


class InProcessResonance:
    def __init__(self, decay: float = 0.95) -> None:
        self._weights: dict[str, float] = {}
        self._decay = decay

    def ingest(self, chunk_id: str, amplitude: list[float], band: str) -> None:
        self._weights[chunk_id] = max(self._weights.get(chunk_id, 0.0), _BAND_AMP.get(band, 1.0))

    def reinforce(self, chunk_id: str) -> None:
        self._weights[chunk_id] = self._weights.get(chunk_id, 1.0) + 1.0  # LTP

    def rank(self, candidate_ids: list[str]) -> list[str]:
        return sorted(candidate_ids, key=lambda c: (-self._weights.get(c, 0.0), c))

    def consolidate(self) -> None:
        # discrete decay pass (the "sleep" heartbeat) — pruning the dormant.
        for c in list(self._weights):
            self._weights[c] *= self._decay
            if self._weights[c] < 0.05:
                del self._weights[c]


# --------------------------------------------------------------------------- #
# PrismLib cache-as-failover stand-in: content-addressed, optionally durable.
# --------------------------------------------------------------------------- #
class DurableCache:
    def __init__(self, path: Optional[str] = None) -> None:
        self._path = Path(path) if path else None
        self._store: dict[str, str] = {}
        if self._path and self._path.exists():
            self._store = json.loads(self._path.read_text(encoding="utf-8"))

    def get(self, key: str) -> Optional[str]:
        return self._store.get(key)

    def has(self, key: str) -> bool:
        return key in self._store

    def put(self, key: str, value: str) -> None:
        self._store[key] = value
        if self._path:  # durable: a frozen answer survives restart / eviction.
            self._path.write_text(json.dumps(self._store), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Chorus / PrismLib cluster stand-in: in-process version broadcast.
# --------------------------------------------------------------------------- #
class InProcessMesh:
    def __init__(self) -> None:
        self.events: list[tuple[int, list[str]]] = []

    def broadcast_version(self, version: GraphVersion, invalidated: list[str]) -> None:
        self.events.append((version.version, invalidated))


# --------------------------------------------------------------------------- #
# Labile working-memory staging buffer.
# --------------------------------------------------------------------------- #
class ListStaging:
    def __init__(self) -> None:
        self._buf: list[tuple[StateDelta, str]] = []

    def stage(self, delta: StateDelta, reason: str) -> None:
        self._buf.append((delta, reason))

    def drain(self) -> list[tuple[StateDelta, str]]:
        out, self._buf = self._buf, []
        return out

    def pending_count(self) -> int:
        return len(self._buf)


# --------------------------------------------------------------------------- #
# Immutable blob storage (local filesystem).
# --------------------------------------------------------------------------- #
class LocalBlobStore:
    def __init__(self, root: str = ".prismcortex_blobs") -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def put(self, data: bytes, modality: str, uri_hint: str = "") -> AssetPointer:
        sha = hashlib.sha256(data).hexdigest()
        path = self._root / sha
        path.write_bytes(data)
        return AssetPointer(asset_id=sha[:16], uri=str(path), modality=modality, sha256=sha)

    def get(self, asset_id: str) -> bytes:
        for p in self._root.iterdir():
            if p.name.startswith(asset_id):
                return p.read_bytes()
        raise KeyError(asset_id)
