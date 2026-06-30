"""Head-to-head: PrismCortex vs Zep Cloud — same workload, real Gemini on PrismCortex side.

Zep uses its managed graph memory API (zep-cloud). Set ZEP_API_KEY to run both sides;
without it, PrismCortex results are measured and Zep dimensions are documented.

Run:
  GEMINI_API_KEY=... python benchmarks/vs_zep.py
  GEMINI_API_KEY=... ZEP_API_KEY=... python benchmarks/vs_zep.py
  python benchmarks/vs_zep.py --json benchmarks/results/competitive/vs_zep.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path

warnings.filterwarnings("ignore")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


FACT = "My deploy budget is 40000 dollars per quarter."
CORR = "Correction: my deploy budget is now 55000 dollars per quarter."
Q = "what is my deploy budget?"


def _gemini_key() -> str:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""


def _has_old_budget(text: str) -> bool:
    t = (text or "").lower()
    return "40000" in t or "40,000" in t or "40k" in t


def _has_new_budget(text: str) -> bool:
    t = (text or "").lower()
    return "55000" in t or "55,000" in t or "55k" in t


def run_prismcortex() -> dict:
    from prismcortex import reference_memory

    pc = reference_memory()
    pc.digest(FACT)
    before = pc.recall(Q).answer
    r1 = pc.recall(Q)
    r2 = pc.recall(Q)
    pc.digest(CORR)
    after = pc.recall(Q).answer
    superseded = len([e for e in pc.store.all_edges() if e.valid_to is not None])
    cert = pc.replay_certificate(Q)
    return {
        "before": before,
        "after": after,
        "correction_surfaces_new": _has_new_budget(after),
        "old_retained": superseded > 0,
        "superseded_count": superseded,
        "replay_identical": r1.answer == r2.answer,
        "cache_hit_on_replay": r2.cache_hit,
        "subgraph_hash": cert.get("subgraph_hash", "")[:32],
        "self_hosted": True,
        "byte_identical_render": r1.answer == r2.answer and r2.cache_hit,
    }


def run_zep(api_key: str) -> dict | None:
    try:
        from zep_cloud.client import Zep
        from zep_cloud.types import Message
    except ImportError:
        print("  [Zep] pip install zep-cloud to enable live comparison")
        return None

    client = Zep(api_key=api_key)
    user_id = f"bench_{uuid.uuid4().hex[:8]}"
    session_id = f"session_{uuid.uuid4().hex[:8]}"
    try:
        client.user.add(user_id=user_id, first_name="Bench", last_name="User")
        client.memory.add_session(user_id=user_id, session_id=session_id)
    except Exception as exc:  # noqa: BLE001
        print(f"  [Zep] setup failed: {exc}")
        return None

    def add_user(text: str) -> None:
        client.memory.add(
            session_id=session_id,
            messages=[Message(role="Bench User", role_type="user", content=text)],
        )

    try:
        add_user(FACT)
        mem_before = client.memory.get(session_id=session_id)
        ctx_before = (mem_before.context or "") if mem_before else ""
        add_user(CORR)
        mem_after = client.memory.get(session_id=session_id)
        ctx_after = (mem_after.context or "") if mem_after else ""
        mem2 = client.memory.get(session_id=session_id)
        ctx2 = (mem2.context or "") if mem2 else ""
    except Exception as exc:  # noqa: BLE001
        print(f"  [Zep] memory API failed: {exc}")
        return None
    finally:
        try:
            client.user.delete(user_id=user_id)
        except Exception:  # noqa: BLE001
            pass

    return {
        "before": ctx_before[:500],
        "after": ctx_after[:500],
        "correction_surfaces_new": _has_new_budget(ctx_after),
        "old_retained": _has_old_budget(ctx_after),
        "replay_identical": ctx_after == ctx2,
        "cache_hit_on_replay": None,
        "self_hosted": False,
        "byte_identical_render": False,
        "note": "Zep returns assembled context string, not a frozen rendered answer",
        "user_id": user_id,
    }


def print_row(label: str, pc_val, zep_val) -> None:
    z = zep_val if zep_val is not None else "(no ZEP_API_KEY)"
    print(f"  {label:28}  PrismCortex: {pc_val!s:40}  Zep: {z!s}")


def build_report(pc: dict, zep: dict | None) -> dict:
    dims = [
        "correction_surfaces_new",
        "old_retained",
        "replay_identical",
        "byte_identical_render",
        "self_hosted",
    ]
    rows = {}
    for d in dims:
        rows[d] = {"prismcortex": pc.get(d), "zep": (zep or {}).get(d)}
    return {
        "benchmark": "correction_workload",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "workload": {"fact": FACT, "correction": CORR, "query": Q},
        "prismcortex": pc,
        "zep": zep,
        "comparison": rows,
        "zep_live": zep is not None,
        "mem0_published_locomo": 91.6,
        "mem0_published_longmemeval": 94.8,
        "zep_published_dmr": 94.8,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default="", help="Write machine-readable report")
    args = parser.parse_args()

    if not _gemini_key():
        sys.exit("Set GEMINI_API_KEY for the PrismCortex side.")

    zep_key = os.environ.get("ZEP_API_KEY", "")

    print("=== PrismCortex vs Zep Cloud — same correction workload ===\n")
    pc = run_prismcortex()
    zep = run_zep(zep_key) if zep_key else None

    print("[1] recall before correction")
    print_row("answer/context", pc["before"][:64], (zep or {}).get("before", "")[:64] if zep else None)

    print("\n[2] correction -> new value surfaces?")
    print_row("shows 55k", pc["correction_surfaces_new"], zep["correction_surfaces_new"] if zep else None)

    print("\n[3] old value (40k) still auditable?")
    print_row("old retained", pc["old_retained"], zep["old_retained"] if zep else None)

    print("\n[4] replay determinism")
    print_row("identical replay", pc["replay_identical"], zep["replay_identical"] if zep else None)
    print_row("byte-identical render", pc["byte_identical_render"], zep["byte_identical_render"] if zep else None)

    print("\n[5] sovereignty")
    print_row("self-hosted option", pc["self_hosted"], zep["self_hosted"] if zep else None)

    print("\n--- honest summary ---")
    print("  Zep +: managed temporal graph, LongMemEval +18.5% (paper), ~200ms retrieval (marketing).")
    print("  Prism +: byte-identical cached *rendered* answers, bitemporal edges, self-host default.")
    if not zep:
        print("\n  Set ZEP_API_KEY + pip install zep-cloud for live Zep numbers on this workload.")

    report = build_report(pc, zep)
    json_path = args.json or str(
        Path(__file__).resolve().parent / "results" / "competitive" / "vs_zep.json"
    )
    Path(json_path).parent.mkdir(parents=True, exist_ok=True)
    Path(json_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n  JSON report -> {json_path}")


if __name__ == "__main__":
    main()
