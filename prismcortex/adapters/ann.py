"""IVF-style ANN retrieval for graphs beyond ~10k nodes (numpy-only, no extra deps)."""
from __future__ import annotations

import os
from typing import Optional

import numpy as np

from .reference import InMemoryGraphStore


class AnnGraphStore(InMemoryGraphStore):
    """In-memory bitemporal store with inverted-file ANN when node count exceeds threshold."""

    def __init__(self, *, tenant_id: str = "default", ivf_threshold: Optional[int] = None, nlist: int = 256, nprobe: int = 16) -> None:
        super().__init__()
        self.tenant_id = tenant_id
        self._ivf_threshold = ivf_threshold or int(os.environ.get("PRISMCORTEX_ANN_THRESHOLD", "5000"))
        self._nlist = nlist
        self._nprobe = nprobe
        self._centroids: Optional[np.ndarray] = None
        self._inverted: list[list[str]] = []
        self._ivf_dirty = True

    def _rebuild_ivf(self) -> None:
        self._ensure_matrix()
        if self._emb_unit is None or len(self._emb_ids) < self._ivf_threshold:
            self._centroids = None
            self._inverted = []
            self._ivf_dirty = False
            return
        n, d = self._emb_unit.shape
        k = min(self._nlist, max(8, n // 40))
        rng = np.random.default_rng(42)
        idx = rng.choice(n, size=k, replace=False)
        self._centroids = self._emb_unit[idx].copy()
        # Lloyd-lite: 3 iterations
        for _ in range(3):
            sims = self._emb_unit @ self._centroids.T
            assign = np.argmax(sims, axis=1)
            for c in range(k):
                mask = assign == c
                if mask.any():
                    self._centroids[c] = self._emb_unit[mask].mean(axis=0)
                    cn = np.linalg.norm(self._centroids[c]) or 1.0
                    self._centroids[c] /= cn
        self._inverted = [[] for _ in range(k)]
        sims = self._emb_unit @ self._centroids.T
        assign = np.argmax(sims, axis=1)
        for i, c in enumerate(assign):
            self._inverted[int(c)].append(self._emb_ids[i])
        self._ivf_dirty = False

    def _ensure_matrix(self) -> None:
        super()._ensure_matrix()
        if self._matrix_dirty:
            self._ivf_dirty = True

    def apply(self, delta):
        v = super().apply(delta)
        self._ivf_dirty = True
        return v

    def retrieve(self, embedding: list[float], k: int = 8):
        if not self._nodes:
            return super().retrieve(embedding, k)
        self._ensure_matrix()
        if self._emb_unit is None:
            return super().retrieve(embedding, k)
        if len(self._emb_ids) < self._ivf_threshold:
            return super().retrieve(embedding, k)
        if self._ivf_dirty:
            self._rebuild_ivf()
        if self._centroids is None:
            return super().retrieve(embedding, k)

        q = np.asarray(embedding, dtype=np.float32)
        qn = float(np.linalg.norm(q)) or 1.0
        q = q / qn
        csim = self._centroids @ q
        n = len(self._emb_ids)
        # Scale probe depth with graph size (more clusters searched at 50k+ nodes).
        nprobe = min(len(csim), max(self._nprobe, n // 2000))
        probe = np.argsort(-csim, kind="stable")[:nprobe]
        candidates: set[str] = set()
        id_to_row = {nid: i for i, nid in enumerate(self._emb_ids)}
        for c in probe:
            for nid in self._inverted[int(c)]:
                candidates.add(nid)
        if not candidates:
            return super().retrieve(embedding, k)

        rows = [id_to_row[nid] for nid in candidates if nid in id_to_row]
        sims = self._emb_unit[rows] @ q
        order = np.argsort(-sims, kind="stable")[: min(k, len(rows))]
        chosen = {self._emb_ids[rows[int(i)]] for i in order}

        edges = [e for e in self._edges.values() if e.is_current and (e.src in chosen or e.dst in chosen)]
        for e in edges:
            chosen.add(e.src)
            chosen.add(e.dst)
        nodes = [self._nodes[n] for n in chosen if n in self._nodes]
        from ..models import Subgraph
        return Subgraph(nodes=nodes, edges=edges)
