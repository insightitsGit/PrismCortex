"""Head-to-head: PrismCortex vs Zep Cloud — same workload, real Gemini on PrismCortex side.

Zep uses its managed graph memory API (zep-cloud). Set ZEP_API_KEY to run both sides;
without it, PrismCortex results are measured and Zep dimensions are documented.

Run:
  GEMINI_API_KEY=... python benchmarks/vs_zep.py
  GEMINI_API_KEY=... ZEP_API_KEY=... python benchmarks/vs_zep.py
"""
from __future__ import annotations

import os
import sys
import uuid
import warnings

warnings.filterwarnings("ignore")

GEMINI = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
ZEP_KEY = os.environ.get("ZEP_API_KEY")
if not GEMINI:
    sys.exit("Set GEMINI_API_KEY for the PrismCortex side.")

from prismcortex import reference_memory  # noqa: E402

FACT = "My deploy budget is 40000 dollars per quarter."
CORR = "Correction: my deploy budget is now 55000 dollars per quarter."
Q = "what is my deploy budget?"


def _has_old_budget(text: str) -> bool:
    t = (text or "").lower()
    return "40000" in t or "40,000" in t or "40k" in t


def _has_new_budget(text: str) -> bool:
    t = (text or "").lower()
    return "55000" in t or "55,000" in t or "55k" in t


def run_prismcortex() -> dict:
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
    }


def run_zep() -> dict | None:
    if not ZEP_KEY:
        return None
    try:
        from zep_cloud.client import Zep
        from zep_cloud.types import Message
    except ImportError:
        print("  [Zep] pip install zep-cloud to enable live comparison")
        return None

    client = Zep(api_key=ZEP_KEY)
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

    return {
        "before": ctx_before[:200],
        "after": ctx_after[:200],
        "correction_surfaces_new": _has_new_budget(ctx_after),
        "old_retained": _has_old_budget(ctx_after),
        "replay_identical": ctx_after == ctx2,
        "cache_hit_on_replay": None,  # Zep returns context string, not byte-identical render cache
        "self_hosted": False,
        "note": "Zep returns assembled context string, not a frozen rendered answer",
    }


def print_row(label: str, pc_val, zep_val) -> None:
    z = zep_val if zep_val is not None else "(no ZEP_API_KEY)"
    print(f"  {label:28}  PrismCortex: {pc_val!s:40}  Zep: {z!s}")


def main() -> None:
    print("=== PrismCortex vs Zep Cloud — same correction workload ===\n")
    pc = run_prismcortex()
    zep = run_zep()

    print("[1] recall before correction")
    print_row("context snippet", pc["before"][:64], (zep or {}).get("before", "")[:64] if zep else None)

    print("\n[2] correction -> new value surfaces?")
    print_row("shows 55k", pc["correction_surfaces_new"], zep["correction_surfaces_new"] if zep else None)

    print("\n[3] old value (40k) still auditable?")
    print_row("old retained", pc["old_retained"], zep["old_retained"] if zep else None)

    print("\n[4] replay determinism")
    print_row("identical replay", pc["replay_identical"], zep["replay_identical"] if zep else None)
    print_row("cached render", pc["cache_hit_on_replay"], zep["cache_hit_on_replay"] if zep else None)

    print("\n[5] sovereignty")
    print_row("self-hosted option", pc["self_hosted"], zep["self_hosted"] if zep else None)

    print("\n--- honest summary ---")
    print("  Zep +: managed graph memory, mature SDK, temporal graph at scale.")
    print("  Prism +: byte-identical cached *rendered* answers, bitemporal edges in-process,")
    print("           full self-host / sovereignty without Neo4j or SaaS dependency.")
    if not zep:
        print("\n  Set ZEP_API_KEY + pip install zep-cloud for live Zep numbers on this workload.")


if __name__ == "__main__":
    main()
