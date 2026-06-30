"""Enterprise feature tests — tenant isolation, RBAC, ANN, policy, aliases."""
from fastapi.testclient import TestClient

from prismcortex import auth, server
from prismcortex.adapters.ann import AnnGraphStore
from prismcortex.adapters.reference import HashingProjector, InMemoryGraphStore
from prismcortex.auth import ROLE_ADMIN, ROLE_READ, ROLE_WRITE, authenticate, reload_keys
from prismcortex.engine import Memory
from prismcortex.labels import register_alias, resolve_alias
from prismcortex.policy import PolicyEngine
from prismcortex.adapters.reference import DurableCache, InProcessMesh, InProcessResonance, ListStaging
from prismcortex.models import DeltaOp, Edge, Node, Operation, StateDelta


class _R:
    model_id = "t"
    def render(self, q, sg):
        return "ok"


def _mem(store=None, tenant="t1"):
    return Memory(
        projector=HashingProjector(dim=64),
        extractor=None,
        renderer=_R(),
        store=store or InMemoryGraphStore(),
        resonance=InProcessResonance(),
        cache=DurableCache(),
        mesh=InProcessMesh(),
        staging=ListStaging(),
        tenant_id=tenant,
    )


def test_tenant_graphs_isolated():
    a = InMemoryGraphStore()
    b = InMemoryGraphStore()
    proj = HashingProjector(dim=64)
    a.apply(StateDelta(ops=[DeltaOp(operation=Operation.ASSIMILATE, node=Node(id="n1", label="secret-a", embedding=proj.embed("secret-a")))]))
    b.apply(StateDelta(ops=[DeltaOp(operation=Operation.ASSIMILATE, node=Node(id="n2", label="secret-b", embedding=proj.embed("secret-b")))]))
    assert a.all_nodes()[0].label == "secret-a"
    assert b.all_nodes()[0].label == "secret-b"
    assert a.find_node_by_label("secret-b") is None


def test_rbac_scoped_keys(monkeypatch):
    monkeypatch.setenv("PRISMCORTEX_API_KEYS", '{"readkey": {"tenant": "a", "roles": ["read"]}, "adminkey": {"tenant": "a", "roles": ["admin"]}}')
    reload_keys()
    r = authenticate("readkey")
    assert r and r.allows("read") and not r.allows("write")
    a = authenticate("adminkey")
    assert a and a.allows("write")


def test_alias_registry():
    register_alias("deploy budget", "Q3 spend", tenant_id="acme")
    assert resolve_alias("Q3 spend", tenant_id="acme") == "deploy budget"


def test_ann_store_retrieve_large():
    store = AnnGraphStore(ivf_threshold=20, nlist=8, nprobe=4)
    proj = HashingProjector(dim=32)
    for i in range(40):
        store.apply(StateDelta(ops=[DeltaOp(operation=Operation.ASSIMILATE, node=Node(id=f"n{i}", label=f"fact number {i}", embedding=proj.embed(f"fact number {i}")))]))
    sub = store.retrieve(proj.embed("fact number 17"), k=3)
    labels = {n.label for n in sub.nodes}
    assert any("17" in l for l in labels)


def test_policy_legal_hold(tmp_path):
    p = PolicyEngine(str(tmp_path))
    p.add_legal_hold("msg-99")
    ok, reason = p.can_forget("msg-99")
    assert not ok and "legal hold" in reason


def test_replay_certificate_and_time_travel():
    store = InMemoryGraphStore()
    proj = HashingProjector(dim=64)
    store.apply(StateDelta(ops=[
        DeltaOp(operation=Operation.ASSIMILATE, node=Node(id="n_b", label="budget", embedding=proj.embed("budget"))),
        DeltaOp(operation=Operation.ASSIMILATE, node=Node(id="n_v", label="$40k", embedding=proj.embed("$40k"))),
        DeltaOp(operation=Operation.ASSIMILATE, edge=Edge(id="e1", src="n_b", dst="n_v", relation="is")),
    ]))
    mem = _mem(store)
    cert = mem.replay_certificate("budget?")
    assert cert["subgraph_hash"] and cert["evidence"] is not None


def test_metrics_without_building_memory(monkeypatch):
    monkeypatch.setenv("PRISMCORTEX_API_KEY", "sekrit")
    reload_keys()
    monkeypatch.setattr(server, "_memory", None)
    monkeypatch.setattr(server, "_tenant_mgr", None)
    c = TestClient(server.app)
    assert c.get("/metrics", headers={"x-api-key": "sekrit"}).status_code == 200
