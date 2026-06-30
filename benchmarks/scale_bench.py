"""Scale + retrieval-quality benchmark (linear scan vs IVF ANN).

Seeds N deterministic synthetic facts (real PrismLang embeddings, NO LLM) and measures
hit@k + retrieval latency as the graph grows. Validates AnnGraphStore at 50k+ facts.

Run:
  python benchmarks/scale_bench.py
  python benchmarks/scale_bench.py --ann --levels 200,1000,10000,50000 --out benchmarks/results/scale_ann.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from prismcortex.adapters.ann import AnnGraphStore
from prismcortex.adapters.prism import PrismLangProjector
from prismcortex.adapters.reference import InMemoryGraphStore
from prismcortex.models import DeltaOp, Edge, Node, Operation, StateDelta

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


def make_store(*, use_ann: bool, ann_threshold: int) -> InMemoryGraphStore:
    if use_ann:
        return AnnGraphStore(tenant_id="scale", ivf_threshold=ann_threshold)
    return InMemoryGraphStore()


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
    return {
        "queries": len(qs),
        "hit_at_k": round(hits / len(qs), 3),
        "answer_present": round(edge_hits / len(qs), 3),
        "retrieve_p50_ms": _pct(lat, 50),
        "retrieve_p95_ms": _pct(lat, 95),
        "retrieve_p99_ms": _pct(lat, 99),
    }


def run_benchmark(
    levels: list[int],
    *,
    use_ann: bool = False,
    ann_threshold: int = 5000,
    sample: int = 200,
    k: int = 8,
) -> dict:
    proj = PrismLangProjector(tenant_id="scale")
    store = make_store(use_ann=use_ann, ann_threshold=ann_threshold)
    mode = "ann" if use_ann else "linear"
    rows = []
    built = 0
    t_all = time.perf_counter()
    for lvl in levels:
        seed_s = build(store, proj, built, lvl)
        per = round(seed_s / (lvl - built) * 1000, 2) if lvl > built else 0
        built = lvl
        r = evaluate(store, proj, lvl, sample=sample, k=k)
        ann_active = use_ann and len(store.all_nodes()) >= ann_threshold
        rows.append({
            "facts": lvl,
            "nodes": len(store.all_nodes()),
            "edges": len(store.all_edges()),
            "seed_ms_per_fact": per,
            "ann_active": ann_active,
            **r,
        })
    return {
        "mode": mode,
        "ann_threshold": ann_threshold if use_ann else None,
        "embedding_dim": proj.dim,
        "k": k,
        "sample_queries": sample,
        "duration_s": round(time.perf_counter() - t_all, 2),
        "levels": rows,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="PrismCortex scale + ANN retrieval benchmark")
    p.add_argument("--ann", action="store_true", help="Use AnnGraphStore (IVF)")
    p.add_argument("--levels", default="200,1000,3000,10000,50000", help="Comma-separated fact counts")
    p.add_argument("--threshold", type=int, default=int(os.environ.get("PRISMCORTEX_ANN_THRESHOLD", "5000")))
    p.add_argument("--sample", type=int, default=200)
    p.add_argument("--k", type=int, default=8)
    p.add_argument("--out", default="", help="Write JSON results to path")
    args = p.parse_args()
    levels = [int(x.strip()) for x in args.levels.split(",") if x.strip()]
    result = run_benchmark(levels, use_ann=args.ann, ann_threshold=args.threshold, sample=args.sample, k=args.k)

    print(f"Scale benchmark — mode={result['mode']}, dim={result['embedding_dim']}, k={args.k}, no LLM\n")
    print(f"{'facts':>7} {'nodes':>7} {'ann':>5} {'hit@k':>7} {'answer':>7} {'p50':>9} {'p95':>9} {'p99':>9}")
    for row in result["levels"]:
        print(f"{row['facts']:>7} {row['nodes']:>7} {str(row['ann_active']):>5} {row['hit_at_k']:>7} "
              f"{row['answer_present']:>7} {row['retrieve_p50_ms']:>8}ms {row['retrieve_p95_ms']:>8}ms "
              f"{row['retrieve_p99_ms']:>8}ms")

    out = args.out or (f"benchmarks/results/scale_{result['mode']}.json" if args.ann or args.out == "" else "")
    if out:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nWrote {path}")

    # GA bar: 50k facts with ANN — published run; tune nprobe if below target
    if args.ann and levels and max(levels) >= 50000:
        last = result["levels"][-1]
        recall_ok = last["hit_at_k"] >= 0.85
        lat_ok = last["retrieve_p95_ms"] <= 80.0
        ok = recall_ok and lat_ok
        print(f"\n50k+ ANN gate: {'PASS' if ok else 'NEEDS WORK'} "
              f"(hit@8={last['hit_at_k']}, p95={last['retrieve_p95_ms']}ms)")
        if not ok and os.environ.get("SCALE_BENCH_STRICT") == "1":
            sys.exit(1)


if __name__ == "__main__":
    main()
