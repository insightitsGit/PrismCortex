"""The Memory engine — the single front door (`digest` / `recall` / `sleep`).

All five Prism packages live behind ports; this class owns the lifecycle logic that
none of them own individually: salience routing, the in-RAM delta calculation, the
fast/slow (inline vs staging) split, bitemporal commits, and the content-addressed
deterministic render path.
"""
from __future__ import annotations

import hashlib
from typing import Optional

from . import salience
from .determinism import content_address, extraction_memo_key
from .models import (
    Band,
    DeltaOp,
    DigestOutcome,
    DigestResult,
    Edge,
    Evidence,
    Explanation,
    FAST_TRACK_BANDS,
    SKIP_BANDS,
    ExtractedGist,
    GraphVersion,
    Node,
    Operation,
    Provenance,
    RecallResult,
    StateDelta,
    Subgraph,
)


def _confidence(weight: float) -> float:
    """Map reinforcement (edge/subject weight) to a 0..1 confidence. A fact stated once
    (weight 1.0) → 0.5; confirmed repeatedly → approaches 1.0."""
    return round(1.0 - 0.5 ** max(weight, 0.0), 3)


from .labels import (
    canonical_label,
    looks_like_correctable_value,
    norm_relation,
    relations_compatible,
    resolve_alias,
)
from .ports import (
    EntityExtractor,
    GistProjector,
    GraphStore,
    MeshBroadcast,
    Renderer,
    ResonanceEngine,
    ResponseCache,
    StagingBuffer,
)


def _node_id(label: str) -> str:
    return "n_" + hashlib.blake2b(label.strip().lower().encode(), digest_size=8).hexdigest()


def _edge_id(src: str, relation: str, dst: str) -> str:
    raw = f"{src}|{relation}|{dst}".encode()
    return "e_" + hashlib.blake2b(raw, digest_size=8).hexdigest()


class Memory:
    """Deterministic, auditable agent memory.

    >>> mem = reference_memory()            # see prismcortex.factory
    >>> mem.digest("My deploy budget is $40k.")
    >>> mem.recall("What's my deploy budget?").answer
    """

    def __init__(
        self,
        *,
        projector: GistProjector,
        extractor: EntityExtractor,
        renderer: Renderer,
        store: GraphStore,
        resonance: ResonanceEngine,
        cache: ResponseCache,
        mesh: MeshBroadcast,
        staging: StagingBuffer,
        template_id: str = "render-v1",
        k: int = 8,
        resolve_threshold: float = 0.88,
        max_facts: Optional[int] = None,
        tenant_id: str = "default",
    ) -> None:
        self.projector = projector
        self.extractor = extractor
        self.renderer = renderer
        self.store = store
        self.resonance = resonance
        self.cache = cache
        self.mesh = mesh
        self.staging = staging
        self.template_id = template_id
        self.k = k
        self.resolve_threshold = resolve_threshold
        self.max_facts = max_facts
        self.tenant_id = tenant_id

    # ------------------------------------------------------------------ write
    def digest(self, text: str, *, source_id: Optional[str] = None, agent_id: Optional[str] = None) -> DigestResult:
        band = salience.assess(text)
        if band in SKIP_BANDS:  # cost gate: never call the LLM on "ok thanks"
            return DigestResult(outcome=DigestOutcome.SKIPPED, band=band, version=self.store.version(), reason="low salience")

        memo = extraction_memo_key(text, self.extractor.model_id)
        if self.cache.has(memo):  # idempotent: identical input never re-digested
            return DigestResult(outcome=DigestOutcome.SKIPPED, band=band, version=self.store.version(), reason="already digested (idempotent)")

        emb = self.projector.embed(text)
        context = self.store.retrieve(emb, k=self.k)
        gist = self.extractor.extract(text, context)

        prov = Provenance(
            source_id=source_id or hashlib.blake2b(text.encode(), digest_size=8).hexdigest(),
            agent_id=agent_id,
        )
        delta, uncertain = self._calculate_delta(gist, context, band, prov)
        self.cache.put(memo, "1")  # mark digested

        if delta.is_empty:
            return DigestResult(outcome=DigestOutcome.SKIPPED, band=band, version=self.store.version(), reason="no new knowledge")

        # Uncertain writes are deferred to sleep() — unless salience fast-tracks them.
        if uncertain and band not in FAST_TRACK_BANDS:
            self.staging.stage(delta, reason=f"uncertain: {gist.notes[:80]}")
            return DigestResult(outcome=DigestOutcome.STAGED, band=band, delta=delta, version=self.store.version(), reason="parked for consolidation")

        version = self._commit(delta)
        only_reinforce = all(op.operation is Operation.REINFORCE for op in delta.ops)
        outcome = DigestOutcome.REINFORCED if only_reinforce else DigestOutcome.COMMITTED
        return DigestResult(outcome=outcome, band=band, delta=delta, version=version)

    def _label_for(self, node_id: str) -> Optional[str]:
        if hasattr(self.store, "node_label"):
            return self.store.node_label(node_id)
        nodes = self.store.all_nodes() if hasattr(self.store, "all_nodes") else []
        for n in nodes:
            if n.id == node_id:
                return n.label
        return None

    def _resolve_subject(self, label: str, resolved: dict[str, str], ops: list[DeltaOp]) -> str:
        """Subject coref: alias → exact → canonical → token overlap → embedding similarity."""
        key = label.strip().lower()
        canon = resolve_alias(label, tenant_id=self.tenant_id)
        for probe in (key, canon):
            if probe in resolved:
                return resolved[probe]

        emb = self.projector.embed(label)
        nid = self.store.find_node_by_label(label)
        if nid is None:
            nid = self.store.find_node_by_label(canon)
        if nid is None and hasattr(self.store, "find_node_by_token_overlap"):
            nid = self.store.find_node_by_token_overlap(label, threshold=0.34)
        if nid is None:
            nid = self.store.find_similar_node(emb, self.resolve_threshold)

        if nid:
            ops.append(DeltaOp(operation=Operation.REINFORCE, target_id=nid, reason="resolved to existing"))
        else:
            kind, attributes = self._ent_meta.get(key, self._ent_meta.get(canon, ("entity", {})))
            nid = _node_id(canon if canon else label)
            ops.append(DeltaOp(
                operation=Operation.ASSIMILATE,
                node=Node(id=nid, label=label, kind=kind, attributes=attributes or {},
                          embedding=emb, band=self._band, provenance=self._prov),
            ))
        resolved[key] = nid
        if canon != key:
            resolved[canon] = nid
        return nid

    def _prior_conflicting_edge(self, src_id: str, relation: str, dst_id: str, *, dst_label: str = "") -> Optional[Edge]:
        """Find a current edge from `src` that this new fact would contradict.

        Matches on normalized relation *or* subject + correctable-value kind so extraction
        drift ("is scheduled for March" vs "scheduled for June") still consolidates.
        """
        if not hasattr(self.store, "current_edges_from"):
            prior = self.store.current_edge(src_id, relation)
            return prior if prior is not None and prior.dst != dst_id else None

        new_val = dst_label or self._label_for(dst_id) or ""
        for e in self.store.current_edges_from(src_id):
            if e.dst == dst_id:
                continue
            if relations_compatible(e.relation, relation):
                return e
            old_label = self._label_for(e.dst) or ""
            if (new_val and old_label
                    and looks_like_correctable_value(new_val)
                    and looks_like_correctable_value(old_label)):
                return e
        return None

    def _prior_edge(self, src_id: str, relation: str):
        """A current edge from src whose relation matches after normalization."""
        norm = norm_relation(relation)
        if hasattr(self.store, "current_edges_from"):
            for e in self.store.current_edges_from(src_id):
                if norm_relation(e.relation) == norm:
                    return e
            return None
        return self.store.current_edge(src_id, relation)

    def _calculate_delta(self, gist: ExtractedGist, context: Subgraph, band: Band, prov: Provenance):
        """Resolve the gist against current knowledge into graph mutations (in RAM)."""
        ops: list[DeltaOp] = []
        uncertain = False
        resolved: dict[str, str] = {}  # lower(label) -> node_id
        self._ent_meta = {e.label.strip().lower(): (e.kind, e.attributes) for e in gist.entities}
        self._ent_meta.update({canonical_label(e.label): (e.kind, e.attributes) for e in gist.entities})
        self._band = band
        self._prov = prov

        def resolve_value(label: str) -> str:
            key = label.strip().lower()
            if key in resolved:
                return resolved[key]
            emb = self.projector.embed(label)
            nid = self.store.find_node_by_label(label)
            if nid:
                ops.append(DeltaOp(operation=Operation.REINFORCE, target_id=nid, reason="resolved to existing"))
            else:
                kind, attributes = self._ent_meta.get(key, ("entity", {}))
                nid = _node_id(label)
                ops.append(DeltaOp(
                    operation=Operation.ASSIMILATE,
                    node=Node(id=nid, label=label, kind=kind, attributes=attributes or {},
                              embedding=emb, band=band, provenance=prov),
                ))
            resolved[key] = nid
            return nid

        # Subjects (relation src) coref by similarity + token overlap; values exact only.
        for rel in gist.relations:
            src_id = self._resolve_subject(rel.src, resolved, ops)
            dst_id = resolve_value(rel.dst)
            new_edge = Edge(id=_edge_id(src_id, rel.relation, dst_id), src=src_id, dst=dst_id, relation=rel.relation, band=band, provenance=prov)
            prior = self._prior_conflicting_edge(src_id, rel.relation, dst_id, dst_label=rel.dst)

            if gist.is_correction:
                if prior is not None:
                    ops.append(DeltaOp(operation=Operation.ACCOMMODATE, edge=new_edge, target_id=prior.id, reason="correction"))
                else:
                    ops.append(DeltaOp(operation=Operation.ASSIMILATE, edge=new_edge, reason="claimed correction, no prior"))
                    uncertain = True
            else:
                if prior is not None:
                    ops.append(DeltaOp(operation=Operation.ASSIMILATE, edge=new_edge, reason="conflicts with existing fact"))
                    uncertain = True
                else:
                    ops.append(DeltaOp(operation=Operation.ASSIMILATE, edge=new_edge))

        for ent in gist.entities:
            resolve_value(ent.label)

        return StateDelta(ops=ops), uncertain

    def _commit(self, delta: StateDelta):
        version = self.store.apply(delta)
        invalidated: list[str] = []
        for op in delta.ops:
            if op.operation is Operation.ASSIMILATE and op.node is not None:
                self.resonance.ingest(op.node.id, op.node.embedding or [], op.node.band.value)
                invalidated.append(op.node.id)
            elif op.operation is Operation.REINFORCE and op.target_id:
                self.resonance.reinforce(op.target_id)
        self.mesh.broadcast_version(version, invalidated)
        return version

    # ------------------------------------------------------------------- read
    def _evidence(self, subgraph: Subgraph) -> list[Evidence]:
        """The audit trail behind an answer: each current fact + its source + confidence."""
        id2label = {n.id: n.label for n in subgraph.nodes}
        id2weight = {n.id: n.weight for n in subgraph.nodes}
        out: list[Evidence] = []
        for e in subgraph.edges:
            if not e.is_current:
                continue
            w = id2weight.get(e.src, e.weight)
            prov = e.provenance
            out.append(Evidence(
                fact=f"{id2label.get(e.src, e.src)} {e.relation} {id2label.get(e.dst, e.dst)}",
                source_id=prov.source_id if prov else None,
                recorded_at=prov.recorded_at if prov else e.recorded_at,
                confirmations=w,
                confidence=_confidence(w),
            ))
        return out

    def _confidence_freshness(self, subgraph: Subgraph):
        weights = {n.id: n.weight for n in subgraph.nodes}
        cur = [e for e in subgraph.edges if e.is_current]
        if not cur:
            return 1.0, None
        conf = round(sum(_confidence(weights.get(e.src, e.weight)) for e in cur) / len(cur), 3)
        fresh = max((e.provenance.recorded_at if e.provenance else e.recorded_at) for e in cur)
        return conf, fresh

    def _expand_subgraph(self, subgraph: Subgraph, query: str) -> Subgraph:
        """Pull in nodes whose labels overlap the query — helps recall in crowded graphs."""
        if not hasattr(self.store, "find_nodes_by_label_overlap"):
            return subgraph
        extra = self.store.find_nodes_by_label_overlap(query, threshold=0.34, limit=4)
        if not extra:
            return subgraph
        chosen = {n.id for n in subgraph.nodes} | set(extra)
        edges = list(subgraph.edges)
        if hasattr(self.store, "current_edges_from"):
            seen = {e.id for e in edges}
            for nid in extra:
                for e in self.store.current_edges_from(nid):
                    if e.is_current and e.id not in seen:
                        edges.append(e)
                        seen.add(e.id)
                        chosen.add(e.src)
                        chosen.add(e.dst)
        nodes = subgraph.nodes
        have = {n.id for n in nodes}
        if hasattr(self.store, "node_label"):
            for nid in chosen:
                if nid not in have and self.store.node_label(nid):
                    label = self.store.node_label(nid)
                    emb = self.projector.embed(label) if label else None
                    nodes = nodes + [Node(id=nid, label=label, embedding=emb)]
                    have.add(nid)
        elif hasattr(self.store, "all_nodes"):
            by_id = {n.id: n for n in self.store.all_nodes()}
            for nid in chosen:
                if nid not in have and nid in by_id:
                    nodes = nodes + [by_id[nid]]
                    have.add(nid)
        return Subgraph(nodes=nodes, edges=edges)

    def recall(self, query: str) -> RecallResult:
        emb = self.projector.embed(query)
        version = self.store.version()
        subgraph = self._expand_subgraph(self.store.retrieve(emb, k=self.k), query)
        key = content_address(query, subgraph, self.template_id, self.renderer.model_id)
        ans_key = "ans:" + key

        node_ids = [n.id for n in subgraph.nodes]
        edge_ids = [e.id for e in subgraph.edges if e.is_current]
        conf, fresh = self._confidence_freshness(subgraph)
        common = dict(subgraph_hash=key, version=version.version, model_id=self.renderer.model_id,
                      node_ids=node_ids, edge_ids=edge_ids, confidence=conf, freshness=fresh)

        cached = self.cache.get(ans_key)
        if cached is not None:
            return RecallResult(answer=cached, cache_hit=True, **common)

        answer = self.renderer.render(query, subgraph)  # the one stochastic draw
        self.cache.put(ans_key, answer)                 # frozen → byte-identical hereafter
        return RecallResult(answer=answer, cache_hit=False, **common)

    def forget(self, source_id: str) -> dict:
        """Right-to-be-forgotten: erase every fact derived from `source_id` and clear the
        answer cache (so deleted content can't linger in a cached response). Returns the
        audit receipt; the erased content is gone, only the tombstone remains."""
        receipt = self.store.forget_source(source_id)
        if hasattr(self.cache, "clear"):
            self.cache.clear()  # cached answers may contain the erased content
        self.mesh.broadcast_version(self.store.version(), invalidated=[])
        return receipt

    def conflicts(self) -> list[dict]:
        """Surface contested facts — subjects with >1 current value for the same
        (normalized) relation — so the system never *silently* serves one of them."""
        from collections import defaultdict

        edges = self.store.all_edges() if hasattr(self.store, "all_edges") else []
        labels = {n.id: n.label for n in (self.store.all_nodes() if hasattr(self.store, "all_nodes") else [])}
        groups: dict[tuple, list] = defaultdict(list)
        for e in edges:
            if e.valid_to is None:
                groups[(e.src, norm_relation(e.relation))].append(e)
        out = []
        for (src, rel), es in groups.items():
            if len({e.dst for e in es}) > 1:
                out.append({"subject": labels.get(src, src), "relation": rel,
                            "values": [labels.get(e.dst, e.dst) for e in es]})
        return out

    def explain(self, query: str) -> Explanation:
        """Why an answer is what it is — the exact facts, sources, and confidence behind it.
        A vector store can return memories; only a provenance graph can return evidence."""
        emb = self.projector.embed(query)
        version = self.store.version()
        subgraph = self._expand_subgraph(self.store.retrieve(emb, k=self.k), query)
        key = content_address(query, subgraph, self.template_id, self.renderer.model_id)
        conf, fresh = self._confidence_freshness(subgraph)
        return Explanation(query=query, version=version.version, subgraph_hash=key,
                           confidence=conf, freshness=fresh, evidence=self._evidence(subgraph))

    # ----------------------------------------------------------------- sleep
    def sleep(self) -> int:
        """Consolidation pass: drain the labile buffer and resolve conflicts off the hot
        path. A staged edge that conflicts with the (now-)current fact for the same
        (subject, relation) is turned into an accommodation — the old fact is invalidated
        (kept for time-travel) and the staged one becomes current. Returns the number of
        staged items consolidated.
        """
        drained = self.staging.drain()
        if drained:
            resolved_ops: list[DeltaOp] = []
            pending: dict[tuple, str] = {}  # (src, norm_relation) -> latest edge id this pass
            for delta, _reason in drained:
                for op in delta.ops:
                    if op.operation is Operation.ASSIMILATE and op.edge is not None:
                        key = (op.edge.src, norm_relation(op.edge.relation))
                        prior_id = pending.get(key)
                        if prior_id is None:  # also resolve against the committed store
                            prior = self._prior_edge(op.edge.src, op.edge.relation)
                            prior_id = prior.id if prior else None
                        pending[key] = op.edge.id
                        if prior_id and prior_id != op.edge.id:
                            resolved_ops.append(DeltaOp(
                                operation=Operation.ACCOMMODATE, edge=op.edge,
                                target_id=prior_id, reason="consolidated conflict",
                            ))
                            continue
                    resolved_ops.append(op)
            if resolved_ops:
                self._commit(StateDelta(ops=resolved_ops))
        self.resonance.consolidate()  # discrete decay heartbeat → new version semantics
        if self.max_facts and hasattr(self.store, "prune_to"):
            # bound the active working set: soft-invalidate the coldest facts (kept for
            # audit/time-travel, out of the recall path) so memory size plateaus.
            self.store.prune_to(self.max_facts)
        return len(drained)

    # ----------------------------------------------------------- enterprise API
    def subgraph_at(self, query: str, at) -> Subgraph:
        """Facts valid at a point in time (bitemporal time-travel)."""
        from datetime import datetime, timezone

        if at is None:
            return self._expand_subgraph(self.store.retrieve(self.projector.embed(query), k=self.k), query)
        if isinstance(at, str):
            at = datetime.fromisoformat(at.replace("Z", "+00:00"))
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        emb = self.projector.embed(query)
        live = self.store.retrieve(emb, k=max(self.k, 16))
        id2label = {n.id: n.label for n in live.nodes}
        for n in (self.store.all_nodes() if hasattr(self.store, "all_nodes") else []):
            id2label[n.id] = n.label
        nodes_map = {n.id: n for n in live.nodes}
        edges = []
        for e in (self.store.all_edges() if hasattr(self.store, "all_edges") else []):
            vf = e.valid_from if e.valid_from.tzinfo else e.valid_from.replace(tzinfo=timezone.utc)
            vt = e.valid_to
            if vt is not None and vt.tzinfo is None:
                vt = vt.replace(tzinfo=timezone.utc)
            if vf <= at and (vt is None or at < vt):
                edges.append(e)
                for nid in (e.src, e.dst):
                    if nid not in nodes_map and hasattr(self.store, "all_nodes"):
                        for n in self.store.all_nodes():
                            if n.id == nid:
                                nodes_map[nid] = n
        return Subgraph(nodes=list(nodes_map.values()), edges=edges)

    def recall_at(self, query: str, at=None) -> RecallResult:
        subgraph = self.subgraph_at(query, at)
        key = content_address(query, subgraph, self.template_id, self.renderer.model_id)
        conf, fresh = self._confidence_freshness(subgraph)
        answer = self.renderer.render(query, subgraph)
        return RecallResult(
            answer=answer, cache_hit=False, subgraph_hash=key,
            version=self.store.version().version, model_id=self.renderer.model_id,
            node_ids=[n.id for n in subgraph.nodes],
            edge_ids=[e.id for e in subgraph.edges],
            confidence=conf, freshness=fresh,
        )

    def replay_certificate(self, query: str) -> dict:
        """Exportable proof: answer + content address + evidence (audit/replay)."""
        ex = self.explain(query)
        rec = self.recall(query)
        return {
            "query": query,
            "answer": rec.answer,
            "cache_hit": rec.cache_hit,
            "subgraph_hash": rec.subgraph_hash,
            "version": rec.version,
            "model_id": rec.model_id,
            "confidence": rec.confidence,
            "freshness": rec.freshness.isoformat() if rec.freshness else None,
            "evidence": [e.model_dump(mode="json") for e in ex.evidence],
        }

    def resolve_conflict(self, subject: str, relation: str, chosen_value: str) -> GraphVersion:
        """Human-in-the-loop: pick the winning value for a contested (subject, relation)."""
        src_id = self.store.find_node_by_label(subject) or self.store.find_node_by_label(resolve_alias(subject, tenant_id=self.tenant_id))
        if src_id is None and hasattr(self.store, "find_node_by_token_overlap"):
            src_id = self.store.find_node_by_token_overlap(subject, threshold=0.34)
        if src_id is None:
            raise ValueError(f"unknown subject: {subject!r}")
        dst_id = self.store.find_node_by_label(chosen_value)
        if dst_id is None:
            emb = self.projector.embed(chosen_value)
            dst_id = _node_id(chosen_value)
            ops = [DeltaOp(operation=Operation.ASSIMILATE, node=Node(id=dst_id, label=chosen_value, embedding=emb))]
        else:
            ops = []
        prior = self._prior_conflicting_edge(src_id, relation, dst_id, dst_label=chosen_value)
        if prior is None:
            raise ValueError("no conflict found for that subject/relation")
        edge = Edge(id=_edge_id(src_id, relation, dst_id), src=src_id, dst=dst_id, relation=relation)
        ops.append(DeltaOp(operation=Operation.ACCOMMODATE, edge=edge, target_id=prior.id, reason="human resolved"))
        return self._commit(StateDelta(ops=ops))
