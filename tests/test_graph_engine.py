"""Deterministic-substrate tests — no LLM, no randomness, real domain objects.

These cover the parts PrismCortex itself owns: bitemporal mutation, the content-address
contract, durable caching, staging, salience routing, and reinforcement.
"""
from datetime import timedelta

from prismcortex.adapters.reference import (
    DurableCache,
    HashingProjector,
    InMemoryGraphStore,
    InProcessMesh,
    InProcessResonance,
    ListStaging,
)
from prismcortex.engine import Memory
from prismcortex.determinism import content_address
from prismcortex.models import (
    Band,
    DeltaOp,
    Edge,
    Node,
    Operation,
    Provenance,
    SKIP_BANDS,
    StateDelta,
    Subgraph,
)


class _R:  # minimal renderer stand-in for graph-only tests (no LLM is invoked here)
    model_id = "test-model"
from prismcortex import salience


def _node(label, **attrs):
    return Node(id="n_" + label, label=label, embedding=HashingProjector().embed(label), attributes=attrs)


def _budget_edge(dst_id, eid="e1"):
    return Edge(id=eid, src="n_amin", dst=dst_id, relation="budget_is")


def test_bitemporal_accommodate_never_destroys():
    store = InMemoryGraphStore()
    store.apply(StateDelta(ops=[
        DeltaOp(operation=Operation.ASSIMILATE, node=_node("amin")),
        DeltaOp(operation=Operation.ASSIMILATE, node=_node("40k")),
        DeltaOp(operation=Operation.ASSIMILATE, edge=_budget_edge("n_40k", "e_old")),
    ]))
    old = store.current_edge("n_amin", "budget_is")
    assert old is not None and old.dst == "n_40k"

    # correction: invalidate old, add new — old is preserved, not deleted.
    store.apply(StateDelta(ops=[
        DeltaOp(operation=Operation.ASSIMILATE, node=_node("50k")),
        DeltaOp(operation=Operation.ACCOMMODATE, edge=_budget_edge("n_50k", "e_new"), target_id="e_old"),
    ]))

    current = store.current_edge("n_amin", "budget_is")
    assert current.dst == "n_50k" and current.is_current
    history = store.history("n_amin", "budget_is")
    assert len(history) == 2                                   # time-travel: both kept
    assert sum(1 for e in history if e.is_current) == 1        # exactly one current
    invalidated = next(e for e in history if e.id == "e_old")
    assert invalidated.valid_to is not None                    # soft-invalidated, intact


def test_version_increments_and_content_hash_tracks_facts():
    store = InMemoryGraphStore()
    assert store.version().version == 0
    v1 = store.apply(StateDelta(ops=[
        DeltaOp(operation=Operation.ASSIMILATE, node=_node("amin")),
        DeltaOp(operation=Operation.ASSIMILATE, node=_node("40k")),
        DeltaOp(operation=Operation.ASSIMILATE, edge=_budget_edge("n_40k", "e_old")),
    ]))
    assert v1.version == 1 and v1.content_hash
    v2 = store.apply(StateDelta(ops=[
        DeltaOp(operation=Operation.ASSIMILATE, node=_node("50k")),
        DeltaOp(operation=Operation.ACCOMMODATE, edge=_budget_edge("n_50k", "e_new"), target_id="e_old"),
    ]))
    assert v2.version == 2
    assert v2.content_hash != v1.content_hash                  # facts changed → hash changed


def test_content_address_is_deterministic_and_sensitive():
    sub_a = Subgraph(nodes=[_node("amin")], edges=[_budget_edge("n_40k")])
    sub_b = Subgraph(nodes=[_node("amin")], edges=[_budget_edge("n_50k")])

    k1 = content_address("what is my budget", sub_a, "render-v1", "gemini-x")
    k2 = content_address("What  IS my   Budget", sub_a, "render-v1", "gemini-x")  # case/space
    k3 = content_address("what is my budget", sub_b, "render-v1", "gemini-x")     # changed fact
    k4 = content_address("what is my budget", sub_a, "render-v1", "gemini-y")     # model rev

    assert k1 == k2          # normalized query → identical key (cache hit across paraphrase spacing)
    assert k1 != k3          # changed fact → new key → stale answer unreachable
    assert k1 != k4          # pinned model snapshot is part of the address


def test_content_address_ignores_subgraph_ordering():
    n1, n2 = _node("a"), _node("b")
    e1 = Edge(id="e1", src="n_a", dst="n_b", relation="likes")
    e2 = Edge(id="e2", src="n_b", dst="n_a", relation="knows")
    one = Subgraph(nodes=[n1, n2], edges=[e1, e2])
    two = Subgraph(nodes=[n2, n1], edges=[e2, e1])            # same facts, different order
    assert content_address("q", one, "t", "m") == content_address("q", two, "t", "m")


def test_durable_cache_survives_reload(tmp_path):
    path = str(tmp_path / "cache.json")
    c1 = DurableCache(path=path)
    c1.put("ans:abc", "the budget is $40k")
    assert c1.has("ans:abc")

    c2 = DurableCache(path=path)                              # cache-as-failover: reload
    assert c2.get("ans:abc") == "the budget is $40k"


def test_staging_drain_is_one_shot():
    s = ListStaging()
    s.stage(StateDelta(ops=[]), "uncertain")
    s.stage(StateDelta(ops=[]), "conflict")
    assert s.pending_count() == 2
    assert len(s.drain()) == 2
    assert s.pending_count() == 0 and s.drain() == []


def test_salience_routing():
    assert salience.assess("ok thanks") in SKIP_BANDS            # skipped, no LLM call
    assert salience.assess("hi") in SKIP_BANDS
    assert salience.assess("the system is down, urgent!") is Band.EMERGENCY  # flashbulb
    assert salience.assess("actually my budget is now 50k") is Band.ALERT    # correction
    assert salience.assess("my deploy region is us-east-1") is Band.NORMAL


def test_find_similar_node_resolves_and_rejects():
    store = InMemoryGraphStore()
    budget = _node("deploy budget")
    store.apply(StateDelta(ops=[DeltaOp(operation=Operation.ASSIMILATE, node=budget)]))
    # an (almost) identical embedding resolves to the existing node ...
    assert store.find_similar_node(budget.embedding, threshold=0.9) == budget.id
    # ... an unrelated label does not (no false merge)
    unrelated = HashingProjector().embed("xyzzy quux frobnicate widget")
    assert store.find_similar_node(unrelated, threshold=0.9) is None


def test_sleep_resolves_staged_conflict_keeping_history():
    """The #2 two-speed path: a staged conflicting edge is resolved on sleep() by
    invalidating the prior fact (retained) and making the staged one current."""
    store = InMemoryGraphStore()
    store.apply(StateDelta(ops=[
        DeltaOp(operation=Operation.ASSIMILATE, node=_node("ttl")),
        DeltaOp(operation=Operation.ASSIMILATE, node=_node("60")),
        DeltaOp(operation=Operation.ASSIMILATE, edge=Edge(id="e60", src="n_ttl", dst="n_60", relation="is")),
    ]))
    staging = ListStaging()
    staging.stage(StateDelta(ops=[
        DeltaOp(operation=Operation.ASSIMILATE, node=_node("300")),
        DeltaOp(operation=Operation.ASSIMILATE, edge=Edge(id="e300", src="n_ttl", dst="n_300", relation="is")),
    ]), "silent conflict")

    mem = Memory(
        projector=HashingProjector(), extractor=None, renderer=None, store=store,
        resonance=InProcessResonance(), cache=DurableCache(), mesh=InProcessMesh(), staging=staging,
    )
    assert mem.sleep() == 1

    current = store.current_edge("n_ttl", "is")
    assert current is not None and current.dst == "n_300"          # new value is current
    history = store.history("n_ttl", "is")
    assert sum(1 for e in history if e.valid_to is not None) == 1  # old value retained, invalidated


def test_sleep_resolves_both_staged_despite_relation_wording():
    """The adversarial fix: two conflicting facts staged together, with *different*
    relation phrasings, must still be detected as one conflict and resolved."""
    from prismcortex.labels import norm_relation

    assert norm_relation("is scheduled for") == norm_relation("scheduled for")
    store = InMemoryGraphStore()
    proj = HashingProjector()
    store.apply(StateDelta(ops=[
        DeltaOp(operation=Operation.ASSIMILATE, node=Node(id="n_launch", label="launch", embedding=proj.embed("launch"))),
        DeltaOp(operation=Operation.ASSIMILATE, node=Node(id="n_march", label="march", embedding=proj.embed("march"))),
        DeltaOp(operation=Operation.ASSIMILATE, node=Node(id="n_june", label="june", embedding=proj.embed("june"))),
    ]))
    staging = ListStaging()
    staging.stage(StateDelta(ops=[DeltaOp(operation=Operation.ASSIMILATE,
        edge=Edge(id="e1", src="n_launch", dst="n_march", relation="is scheduled for"))]), "c1")
    staging.stage(StateDelta(ops=[DeltaOp(operation=Operation.ASSIMILATE,
        edge=Edge(id="e2", src="n_launch", dst="n_june", relation="scheduled for"))]), "c2")

    mem = Memory(projector=proj, extractor=None, renderer=_R(), store=store,
                 resonance=InProcessResonance(), cache=DurableCache(), mesh=InProcessMesh(), staging=staging)
    mem.sleep()

    current = [e for e in store.all_edges() if e.valid_to is None]
    assert len(current) == 1 and current[0].dst == "n_june"   # latest wins across wording
    assert sum(1 for e in store.all_edges() if e.valid_to is not None) == 1  # old retained


class _FixedProj:
    """Projector with controlled embeddings — to force a value-collision condition."""

    def __init__(self, mapping):
        self._m = mapping

    def embed(self, text):
        return self._m.get(text.strip().lower(), [0.0, 1.0, 0.0])

    def classify(self, text):
        return "general"


def test_values_with_colliding_embeddings_stay_distinct():
    """Regression: a NEW value must never fuzzy-merge into an existing value node even
    when their embeddings collide — only subjects coref. (The bug that broke conflict
    resolution: '300 seconds' merged into '60 seconds'.)"""
    from prismcortex.models import Band, ExtractedEntity, ExtractedGist, ExtractedRelation, Provenance, Subgraph

    store = InMemoryGraphStore()
    store.apply(StateDelta(ops=[
        DeltaOp(operation=Operation.ASSIMILATE, node=Node(id="n_sub", label="cache ttl", embedding=[0.0, 0.0, 1.0])),
        DeltaOp(operation=Operation.ASSIMILATE, node=Node(id="n_60", label="60 seconds", embedding=[1.0, 0.0, 0.0])),
        DeltaOp(operation=Operation.ASSIMILATE, edge=Edge(id="e60", src="n_sub", dst="n_60", relation="is")),
    ]))
    # "300 seconds" embeds IDENTICALLY to "60 seconds" — would merge if dst used fuzzy match
    proj = _FixedProj({"cache ttl": [0.0, 0.0, 1.0], "60 seconds": [1.0, 0.0, 0.0], "300 seconds": [1.0, 0.0, 0.0]})
    mem = Memory(projector=proj, extractor=None, renderer=_R(), store=store,
                 resonance=InProcessResonance(), cache=DurableCache(), mesh=InProcessMesh(), staging=ListStaging())

    gist = ExtractedGist(
        entities=[ExtractedEntity(label="cache ttl"), ExtractedEntity(label="300 seconds")],
        relations=[ExtractedRelation(src="cache ttl", dst="300 seconds", relation="is")],
    )
    delta, uncertain = mem._calculate_delta(gist, Subgraph(), Band.NORMAL, Provenance(source_id="m"))

    new_values = [op.node.label for op in delta.ops if op.operation is Operation.ASSIMILATE and op.node]
    assert "300 seconds" in new_values   # distinct new value, NOT merged into "60 seconds"
    assert uncertain                      # and the 60-vs-300 conflict is detected


def test_explain_returns_evidence_trail():
    store = InMemoryGraphStore()
    proj = HashingProjector()
    store.apply(StateDelta(ops=[
        DeltaOp(operation=Operation.ASSIMILATE, node=Node(id="n_amin", label="amin", embedding=proj.embed("amin"))),
        DeltaOp(operation=Operation.ASSIMILATE, node=Node(id="n_40k", label="$40,000", embedding=proj.embed("$40,000"))),
        DeltaOp(operation=Operation.ASSIMILATE, edge=Edge(id="e1", src="n_amin", dst="n_40k", relation="budget_is",
                provenance=Provenance(source_id="msg-7"))),
    ]))
    mem = Memory(projector=proj, extractor=None, renderer=_R(), store=store,
                 resonance=InProcessResonance(), cache=DurableCache(), mesh=InProcessMesh(), staging=ListStaging())
    ex = mem.explain("what is the budget")
    assert ex.evidence, "explain must return the supporting facts"
    ev = ex.evidence[0]
    assert "budget_is" in ev.fact and ev.source_id == "msg-7"   # traceable to its source
    assert 0.0 <= ex.confidence <= 1.0 and ev.confidence >= 0.0


def test_prune_to_bounds_active_set_but_keeps_history():
    store = InMemoryGraphStore()
    proj = HashingProjector()
    for i in range(10):
        store.apply(StateDelta(ops=[
            DeltaOp(operation=Operation.ASSIMILATE, node=Node(id=f"n{i}", label=f"e{i}", embedding=proj.embed(f"e{i}"))),
            DeltaOp(operation=Operation.ASSIMILATE, node=Node(id=f"v{i}", label=f"x{i}", embedding=proj.embed(f"x{i}"))),
            DeltaOp(operation=Operation.ASSIMILATE, edge=Edge(id=f"e_{i}", src=f"n{i}", dst=f"v{i}", relation="is")),
        ]))
    pruned = store.prune_to(4)
    assert pruned == 6
    assert sum(1 for e in store.all_edges() if e.valid_to is None) == 4   # active set bounded
    assert sum(1 for e in store.all_edges() if e.valid_to is not None) == 6  # history retained


def test_forget_erases_facts_clears_cache_keeps_tombstone():
    store = InMemoryGraphStore()
    proj = HashingProjector()
    src = Provenance(source_id="msg-1")
    store.apply(StateDelta(ops=[
        DeltaOp(operation=Operation.ASSIMILATE, node=Node(id="n_a", label="amin", embedding=proj.embed("amin"), provenance=src)),
        DeltaOp(operation=Operation.ASSIMILATE, node=Node(id="n_40", label="$40k", embedding=proj.embed("$40k"), provenance=src)),
        DeltaOp(operation=Operation.ASSIMILATE, edge=Edge(id="e1", src="n_a", dst="n_40", relation="budget_is", provenance=src)),
    ]))
    cache = DurableCache()
    cache.put("ans:x", "amin's budget is $40k")  # a cached answer containing the content
    mem = Memory(projector=proj, extractor=None, renderer=_R(), store=store,
                 resonance=InProcessResonance(), cache=cache, mesh=InProcessMesh(), staging=ListStaging())

    receipt = mem.forget("msg-1")
    assert receipt["edges_erased"] == 1 and receipt["nodes_erased"] == 2
    assert store.all_edges() == []                 # content gone (GDPR erasure)
    assert cache.get("ans:x") is None              # cached content cleared, can't linger
    assert len(store.tombstones()) == 1            # but the erasure is auditable


def test_conflicts_surfaces_contested_facts():
    store = InMemoryGraphStore()
    proj = HashingProjector()
    store.apply(StateDelta(ops=[
        DeltaOp(operation=Operation.ASSIMILATE, node=Node(id="n_b", label="budget", embedding=proj.embed("budget"))),
        DeltaOp(operation=Operation.ASSIMILATE, node=Node(id="n_40", label="40k", embedding=proj.embed("40k"))),
        DeltaOp(operation=Operation.ASSIMILATE, node=Node(id="n_50", label="50k", embedding=proj.embed("50k"))),
        DeltaOp(operation=Operation.ASSIMILATE, edge=Edge(id="e1", src="n_b", dst="n_40", relation="is")),
        DeltaOp(operation=Operation.ASSIMILATE, edge=Edge(id="e2", src="n_b", dst="n_50", relation="is")),
    ]))
    mem = Memory(projector=proj, extractor=None, renderer=_R(), store=store,
                 resonance=InProcessResonance(), cache=DurableCache(), mesh=InProcessMesh(), staging=ListStaging())
    c = mem.conflicts()
    assert len(c) == 1 and set(c[0]["values"]) == {"40k", "50k"}  # contested, surfaced not hidden


def test_reinforce_raises_weight():
    store = InMemoryGraphStore()
    store.apply(StateDelta(ops=[DeltaOp(operation=Operation.ASSIMILATE, node=_node("amin"))]))
    store.apply(StateDelta(ops=[DeltaOp(operation=Operation.REINFORCE, target_id="n_amin")]))
    sub = store.retrieve(HashingProjector().embed("amin"), k=5)
    amin = next(n for n in sub.nodes if n.id == "n_amin")
    assert amin.weight > 1.0


def test_canonical_label_resolves_the_budget():
    from prismcortex.models import Band, ExtractedEntity, ExtractedGist, ExtractedRelation, Provenance, Subgraph

    store = InMemoryGraphStore()
    proj = HashingProjector()
    store.apply(StateDelta(ops=[
        DeltaOp(operation=Operation.ASSIMILATE, node=Node(id="n_b", label="deploy budget", embedding=proj.embed("deploy budget"))),
        DeltaOp(operation=Operation.ASSIMILATE, node=Node(id="n_v", label="$40,000", embedding=proj.embed("$40,000"))),
        DeltaOp(operation=Operation.ASSIMILATE, edge=Edge(id="e1", src="n_b", dst="n_v", relation="is")),
    ]))
    mem = Memory(projector=proj, extractor=None, renderer=_R(), store=store,
                 resonance=InProcessResonance(), cache=DurableCache(), mesh=InProcessMesh(), staging=ListStaging())
    gist = ExtractedGist(
        entities=[ExtractedEntity(label="the deploy budget"), ExtractedEntity(label="$55,000")],
        relations=[ExtractedRelation(src="the deploy budget", dst="$55,000", relation="is")],
    )
    delta, uncertain = mem._calculate_delta(gist, Subgraph(), Band.NORMAL, Provenance(source_id="m"))
    src_ops = [op for op in delta.ops if op.operation is Operation.REINFORCE]
    assert src_ops and src_ops[0].target_id == "n_b"
    assert uncertain


def test_subject_token_overlap_coref():
    from prismcortex.models import Band, ExtractedEntity, ExtractedGist, ExtractedRelation, Provenance, Subgraph

    store = InMemoryGraphStore()
    proj = HashingProjector()
    store.apply(StateDelta(ops=[
        DeltaOp(operation=Operation.ASSIMILATE, node=Node(id="n_launch", label="product launch", embedding=proj.embed("product launch"))),
    ]))
    mem = Memory(projector=proj, extractor=None, renderer=_R(), store=store,
                 resonance=InProcessResonance(), cache=DurableCache(), mesh=InProcessMesh(), staging=ListStaging())
    gist = ExtractedGist(
        entities=[ExtractedEntity(label="launch"), ExtractedEntity(label="June")],
        relations=[ExtractedRelation(src="launch", dst="June", relation="scheduled for")],
    )
    delta, _ = mem._calculate_delta(gist, Subgraph(), Band.NORMAL, Provenance(source_id="m"))
    edge_ops = [op for op in delta.ops if op.edge]
    assert edge_ops and edge_ops[0].edge.src == "n_launch"


def test_value_conflict_despite_relation_drift():
    from prismcortex.models import Band, ExtractedEntity, ExtractedGist, ExtractedRelation, Provenance, Subgraph

    store = InMemoryGraphStore()
    proj = HashingProjector()
    store.apply(StateDelta(ops=[
        DeltaOp(operation=Operation.ASSIMILATE, node=Node(id="n_launch", label="product launch", embedding=proj.embed("product launch"))),
        DeltaOp(operation=Operation.ASSIMILATE, node=Node(id="n_march", label="March", embedding=proj.embed("March"))),
        DeltaOp(operation=Operation.ASSIMILATE, edge=Edge(id="e1", src="n_launch", dst="n_march", relation="is scheduled for")),
    ]))
    mem = Memory(projector=proj, extractor=None, renderer=_R(), store=store,
                 resonance=InProcessResonance(), cache=DurableCache(), mesh=InProcessMesh(), staging=ListStaging())
    gist = ExtractedGist(
        entities=[ExtractedEntity(label="launch"), ExtractedEntity(label="June")],
        relations=[ExtractedRelation(src="launch", dst="June", relation="date is")],
    )
    delta, uncertain = mem._calculate_delta(gist, Subgraph(), Band.NORMAL, Provenance(source_id="m"))
    assert uncertain
    edge_ops = [op for op in delta.ops if op.edge]
    assert any(op.edge and op.edge.dst and op.reason == "conflicts with existing fact" for op in edge_ops)


def test_crowded_graph_recall_includes_label_overlap():
    store = InMemoryGraphStore()
    proj = HashingProjector()
    for label in ["Acme Corp", "Acme Health", "Boston", "Denver", "React", "Go"]:
        store.apply(StateDelta(ops=[DeltaOp(operation=Operation.ASSIMILATE, node=Node(id=f"n_{label}", label=label, embedding=proj.embed(label)))]))
    store.apply(StateDelta(ops=[
        DeltaOp(operation=Operation.ASSIMILATE, node=Node(id="n_launch", label="product launch", embedding=proj.embed("product launch"))),
        DeltaOp(operation=Operation.ASSIMILATE, node=Node(id="n_june", label="June", embedding=proj.embed("June"))),
        DeltaOp(operation=Operation.ASSIMILATE, edge=Edge(id="e_launch", src="n_launch", dst="n_june", relation="scheduled for")),
    ]))

    class _Render:
        model_id = "test"
        def render(self, query, subgraph):
            parts = [f"{n.label}" for n in subgraph.nodes]
            return " ".join(parts)

    mem = Memory(projector=proj, extractor=None, renderer=_Render(), store=store,
                 resonance=InProcessResonance(), cache=DurableCache(), mesh=InProcessMesh(), staging=ListStaging())
    ans = mem.recall("When is the product launch?").answer.lower()
    assert "june" in ans
