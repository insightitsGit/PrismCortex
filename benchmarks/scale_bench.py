"""Scale + retrieval-quality benchmark.

Does retrieval stay accurate and fast as the graph grows? Seeds N deterministic synthetic
facts directly (real PrismLang embeddings, NO LLM, NO randomness) and measures hit@k +
retrieval latency at increasing N. This isolates the *retrieval* claim — the thing that
actually breaks at scale — from extraction cost. No Gemini key required.

Run:  python benchmarks/scale_bench.py
"""
from __future__ import annotations

import time

from prismcortex.adapters.prism import PrismLangProjector
from prismcortex.adapters.reference import InMemoryGraphStore
from prismcortex.models import DeltaOp, Edge, Node, Operation, StateDelta

# Distinct-but-domain-overlapping vocabulary → realistic retrieval (real distractors).
ADJ = ["agile", "global", "secure", "modular", "unified", "adaptive", "realtime", "hybrid",
       "distributed", "neural", "federated", "elastic", "resilient", "semantic", "autonomous",
       "scalable", "encrypted", "streaming", "predictive", "compliant", "sovereign", "cognitive"]
NOUN = ["analytics", "payments", "logistics", "identity", "inventory", "billing", "routing",
        "forecasting", "onboarding", "compliance", "telemetry", "ledger", "catalog", "scheduling",
        "provisioning", "authentication", "orchestration", "ingestion", "settlement", "moderation",
        "personalization", "observability"]
DOMAIN = ["platform", "service", "pipeline", "gateway", "engine", "fabric", "mesh", "layer",
          "cluster", "module", "workflow", "toolkit", "framework", "runtime", "controller",
          "registry", "broker", "scheduler", "planner", "subsystem"]


def subject(i: int) -> str:
    a = ADJ[i % len(ADJ)]
    n = NOUN[(i // len(ADJ)) % len(NOUN)]
    d = DOMAIN[(i // (len(ADJ) * len(NOUN))) % len(DOMAIN)]
    return f"the {a} {n} {d}"


def query(i: int) -> str:
    return f"who is the lead engineer of {subject(i)}?"


def _pct(vals, p):
    s = sorted(vals)
    return round(s[min(len(s) - 1, int(round((p / 100) * (len(s) - 1))))], 3)


def build(store: InMemoryGraphStore, proj: PrismLangProjector, start: int, end: int) -> float:
    t0 = time.perf_counter()
    for i in range(start, end):
        sid, vid = f"s_{i}", f"v_{i}"
        store.apply(StateDelta(ops=[
            DeltaOp(operation=Operation.ASSIMILATE, node=Node(id=sid, label=subject(i), embedding=proj.embed(subject(i)))),
            DeltaOp(operation=Operation.ASSIMILATE, node=Node(id=vid, label=f"engineer #{i}", embedding=proj.embed(f"engineer #{i}"))),
            DeltaOp(operation=Operation.ASSIMILATE, edge=Edge(id=f"e_{i}", src=sid, dst=vid, relation="lead_is")),
        ]))
    return time.perf_counter() - t0


def evaluate(store: InMemoryGraphStore, proj: PrismLangProjector, n: int, sample: int = 200, k: int = 8):
    step = max(1, n // sample)
    qs = list(range(0, n, step))[:sample]
    hits = edge_hits = 0
    lat = []
    for i in qs:
        emb = proj.embed(query(i))
        t0 = time.perf_counter()
        sub = store.retrieve(emb, k=k)
        lat.append((time.perf_counter() - t0) * 1000)
        nids = {x.id for x in sub.nodes}
        if f"s_{i}" in nids:
            hits += 1
        if any(e.id == f"e_{i}" for e in sub.edges):
            edge_hits += 1
    return {"queries": len(qs), "hit_at_k": round(hits / len(qs), 3),
            "answer_present": round(edge_hits / len(qs), 3),
            "retrieve_p50_ms": _pct(lat, 50), "retrieve_p95_ms": _pct(lat, 95)}


def main():
    levels = [200, 1000, 3000]
    k = 8
    proj = PrismLangProjector(tenant_id="scale")
    store = InMemoryGraphStore()
    print(f"Scale benchmark — real PrismLang embeddings (dim={proj.dim}), k={k}, no LLM\n")
    print(f"{'facts':>7} {'nodes':>7} {'hit@k':>7} {'answer':>7} {'retr p50':>9} {'retr p95':>9} {'seed/fact':>10}")
    built = 0
    for lvl in levels:
        seed_s = build(store, proj, built, lvl)
        per = round(seed_s / (lvl - built) * 1000, 2) if lvl > built else 0
        built = lvl
        r = evaluate(store, proj, lvl, sample=200, k=k)
        print(f"{lvl:>7} {len(store.all_nodes()):>7} {r['hit_at_k']:>7} {r['answer_present']:>7} "
              f"{r['retrieve_p50_ms']:>8}ms {r['retrieve_p95_ms']:>8}ms {per:>8}ms")
    print("\nhit@k = fraction of queries whose target fact is in the top-k retrieved subgraph.")
    print("If hit@k holds and retrieval latency stays flat as facts grow, retrieval scales.")


if __name__ == "__main__":
    main()
