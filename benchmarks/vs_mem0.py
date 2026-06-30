"""Head-to-head: PrismCortex vs Mem0 (OSS) — same workload, same real Gemini model.

Run:
  GEMINI_API_KEY=... python benchmarks/vs_mem0.py
  python benchmarks/vs_mem0.py --json benchmarks/results/competitive/vs_mem0.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

warnings.filterwarnings("ignore")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
if not KEY:
    sys.exit("Set GEMINI_API_KEY — this compares two real systems on real Gemini.")

from mem0 import Memory as Mem0Memory  # noqa: E402

from prismcortex import reference_memory  # noqa: E402

UID = "bench"
FACT = "My deploy budget is 40000 dollars per quarter."
CORR = "Correction: my deploy budget is now 55000 dollars per quarter."
Q = "what is my deploy budget?"
MEM0_CFG = {
    "llm": {"provider": "gemini", "config": {"model": "gemini-2.5-flash", "api_key": KEY}},
    "embedder": {"provider": "gemini", "config": {"model": "models/gemini-embedding-001", "api_key": KEY, "embedding_dims": 1536}},
    "vector_store": {"provider": "qdrant", "config": {"embedding_model_dims": 1536, "on_disk": False}},
}


def mem0_top(mem0, q: str) -> str:
    r = mem0.search(q, filters={"user_id": UID})
    res = r.get("results", r) if isinstance(r, dict) else r
    return (res[0].get("memory") if res else "(none)") or "(none)"


def mem0_all(mem0) -> list[str]:
    r = mem0.get_all(filters={"user_id": UID})
    res = r.get("results", r) if isinstance(r, dict) else r
    return [(x.get("memory") or "") for x in res]


def _has_new(s: str) -> bool:
    t = s.lower()
    return "55000" in t or "55,000" in t or "55k" in t


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default="", help="Write machine-readable report")
    args = parser.parse_args()

    mem0 = Mem0Memory.from_config(MEM0_CFG)
    pc = reference_memory()

    print("=== PrismCortex vs Mem0 (OSS) — same workload, real Gemini ===\n")

    mem0.add(FACT, user_id=UID)
    pc.digest(FACT)

    m_before = mem0_top(mem0, Q)
    pc_before = pc.recall(Q).answer
    print("[1] recall current value")
    print(f"    Mem0       : {m_before[:64]!r}")
    print(f"    PrismCortex: {pc_before[:64]!r}")

    print("\n[2] determinism — same query twice")
    m1, m2 = mem0_top(mem0, Q), mem0_top(mem0, Q)
    a1, a2 = pc.recall(Q), pc.recall(Q)
    print(f"    Mem0       : identical={m1 == m2}")
    print(f"    PrismCortex: identical={a1.answer == a2.answer}  (cache_hit={a2.cache_hit})")

    print("\n[3] correction -> new value")
    mem0.add(CORR, user_id=UID)
    pc.digest(CORR)
    m_after = mem0_top(mem0, Q)
    pc_after = pc.recall(Q).answer
    print(f"    Mem0       : {m_after[:64]!r}")
    print(f"    PrismCortex: {pc_after[:64]!r}")

    print("\n[4] TIME-TRAVEL — old value (40000) still auditable?")
    mem0_has_old = any(("40000" in s or "40,000" in s) for s in mem0_all(mem0))
    pc_superseded = len([e for e in pc.store.all_edges() if e.valid_to is not None])
    print(f"    Mem0       : {'YES' if mem0_has_old else 'NO'}")
    print(f"    PrismCortex: {'YES' if pc_superseded else 'NO'}  ({pc_superseded} superseded edge(s))")

    report = {
        "benchmark": "correction_workload",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "workload": {"fact": FACT, "correction": CORR, "query": Q},
        "mem0": {
            "before": m_before,
            "after": m_after,
            "correction_surfaces_new": _has_new(m_after),
            "old_retained": mem0_has_old,
            "retrieval_identical": m1 == m2,
            "byte_identical_render": False,
            "self_hosted": True,
        },
        "prismcortex": {
            "before": pc_before,
            "after": pc_after,
            "correction_surfaces_new": _has_new(pc_after),
            "old_retained": pc_superseded > 0,
            "superseded_count": pc_superseded,
            "replay_identical": a1.answer == a2.answer,
            "cache_hit_on_replay": a2.cache_hit,
            "byte_identical_render": a1.answer == a2.answer and a2.cache_hit,
            "self_hosted": True,
        },
        "mem0_published_locomo": 91.6,
        "mem0_published_longmemeval": 94.8,
    }

    json_path = args.json or str(Path(__file__).resolve().parent / "results" / "competitive" / "vs_mem0.json")
    Path(json_path).parent.mkdir(parents=True, exist_ok=True)
    Path(json_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n  JSON report -> {json_path}")


if __name__ == "__main__":
    main()
