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
    FAST_TRACK_BANDS,
    SKIP_BANDS,
    ExtractedGist,
    Node,
    Operation,
    Provenance,
    RecallResult,
    StateDelta,
    Subgraph,
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

    def _calculate_delta(self, gist: ExtractedGist, context: Subgraph, band: Band, prov: Provenance):
        """Resolve the gist against current knowledge into graph mutations (in RAM)."""
        ops: list[DeltaOp] = []
        uncertain = False
        resolved: dict[str, str] = {}  # lower(label) -> node_id

        def resolve(label: str, kind: str, attributes: Optional[dict] = None, allow_fuzzy: bool = True) -> str:
            key = label.strip().lower()
            if key in resolved:
                return resolved[key]
            emb = self.projector.embed(label)
            nid = self.store.find_node_by_label(label)
            if nid is None and allow_fuzzy:  # entity resolution: paraphrase -> same node
                nid = self.store.find_similar_node(emb, self.resolve_threshold)
            if nid:
                ops.append(DeltaOp(operation=Operation.REINFORCE, target_id=nid, reason="resolved to existing"))
            else:
                nid = _node_id(label)
                ops.append(DeltaOp(
                    operation=Operation.ASSIMILATE,
                    node=Node(id=nid, label=label, kind=kind, attributes=attributes or {},
                              embedding=emb, band=band, provenance=prov),
                ))
            resolved[key] = nid
            return nid

        for ent in gist.entities:
            resolve(ent.label, ent.kind, ent.attributes)

        for rel in gist.relations:
            src_id = resolve(rel.src, "entity")
            # values stay distinct ($40k != $55k); only subjects resolve by similarity
            dst_id = resolve(rel.dst, "value", allow_fuzzy=False)
            new_edge = Edge(id=_edge_id(src_id, rel.relation, dst_id), src=src_id, dst=dst_id, relation=rel.relation, band=band, provenance=prov)
            prior = self.store.current_edge(src_id, rel.relation)

            if gist.is_correction:
                if prior is not None:
                    ops.append(DeltaOp(operation=Operation.ACCOMMODATE, edge=new_edge, target_id=prior.id, reason="correction"))
                else:  # claims a correction but nothing on record → let sleep investigate
                    ops.append(DeltaOp(operation=Operation.ASSIMILATE, edge=new_edge, reason="claimed correction, no prior"))
                    uncertain = True
            else:
                if prior is not None and prior.dst != dst_id:
                    # silent conflict (new value, not flagged as a fix) → defer to sleep
                    ops.append(DeltaOp(operation=Operation.ASSIMILATE, edge=new_edge, reason="conflicts with existing fact"))
                    uncertain = True
                else:
                    ops.append(DeltaOp(operation=Operation.ASSIMILATE, edge=new_edge))

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
    def recall(self, query: str) -> RecallResult:
        emb = self.projector.embed(query)
        version = self.store.version()
        subgraph = self.store.retrieve(emb, k=self.k)
        key = content_address(query, subgraph, self.template_id, self.renderer.model_id)
        ans_key = "ans:" + key

        node_ids = [n.id for n in subgraph.nodes]
        edge_ids = [e.id for e in subgraph.edges if e.is_current]

        cached = self.cache.get(ans_key)
        if cached is not None:
            return RecallResult(answer=cached, cache_hit=True, subgraph_hash=key, version=version.version, model_id=self.renderer.model_id, node_ids=node_ids, edge_ids=edge_ids)

        answer = self.renderer.render(query, subgraph)  # the one stochastic draw
        self.cache.put(ans_key, answer)                 # frozen → byte-identical hereafter
        return RecallResult(answer=answer, cache_hit=False, subgraph_hash=key, version=version.version, model_id=self.renderer.model_id, node_ids=node_ids, edge_ids=edge_ids)

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
            for delta, _reason in drained:
                for op in delta.ops:
                    if op.operation is Operation.ASSIMILATE and op.edge is not None:
                        prior = self.store.current_edge(op.edge.src, op.edge.relation)
                        if prior is not None and prior.dst != op.edge.dst and prior.id != op.edge.id:
                            resolved_ops.append(DeltaOp(
                                operation=Operation.ACCOMMODATE, edge=op.edge,
                                target_id=prior.id, reason="consolidated conflict",
                            ))
                            continue
                    resolved_ops.append(op)
            if resolved_ops:
                self._commit(StateDelta(ops=resolved_ops))
        self.resonance.consolidate()  # discrete decay heartbeat → new version semantics
        return len(drained)
