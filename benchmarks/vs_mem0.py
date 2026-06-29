"""Head-to-head: PrismCortex vs Mem0 (OSS) — same workload, same real Gemini model.

Fair and honest: it compares on the dimensions PrismCortex claims as differentiators
(deterministic cached answers, time-travel/audit) and is explicit where Mem0 is even or
ahead (maturity, vector retrieval is also deterministic, easier with OpenAI defaults).

Run:  GEMINI_API_KEY=...  python benchmarks/vs_mem0.py
"""
from __future__ import annotations

import os
import sys
import warnings

warnings.filterwarnings("ignore")
KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
if not KEY:
    sys.exit("Set GEMINI_API_KEY — this compares two real systems on real Gemini.")

from mem0 import Memory as Mem0Memory  # noqa: E402

from prismcortex import reference_memory  # noqa: E402

UID = "bench"
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


def main() -> None:
    mem0 = Mem0Memory.from_config(MEM0_CFG)
    pc = reference_memory()
    Q = "what is my deploy budget?"

    print("=== PrismCortex vs Mem0 (OSS) — same workload, real Gemini ===\n")

    fact = "My deploy budget is 40000 dollars per quarter."
    mem0.add(fact, user_id=UID)
    pc.digest(fact)

    print("[1] recall current value")
    print(f"    Mem0       : {mem0_top(mem0, Q)[:64]!r}")
    print(f"    PrismCortex: {pc.recall(Q).answer[:64]!r}")

    print("\n[2] determinism — same query twice")
    m1, m2 = mem0_top(mem0, Q), mem0_top(mem0, Q)
    a1, a2 = pc.recall(Q), pc.recall(Q)
    print(f"    Mem0       : identical={m1 == m2}  (vector retrieval, deterministic; returns raw memory, not a rendered answer)")
    print(f"    PrismCortex: identical={a1.answer == a2.answer}  (cache_hit={a2.cache_hit}; rendered answer frozen, 0 extra model calls)")

    print("\n[3] correction -> new value")
    corr = "Correction: my deploy budget is now 55000 dollars per quarter."
    mem0.add(corr, user_id=UID)
    pc.digest(corr)
    print(f"    Mem0       : {mem0_top(mem0, Q)[:64]!r}")
    print(f"    PrismCortex: {pc.recall(Q).answer[:64]!r}")

    print("\n[4] TIME-TRAVEL — is the OLD value (40000) still an auditable, queryable fact?")
    mem0_has_old = any(("40000" in s or "40,000" in s) for s in mem0_all(mem0))
    pc_superseded = [e for e in pc.store.all_edges() if e.valid_to is not None]
    print(f"    Mem0       : {'YES' if mem0_has_old else 'NO'}  (OSS updates in place; temporal retrieval is a paid Platform feature)")
    print(f"    PrismCortex: {'YES' if pc_superseded else 'NO'}  ({len(pc_superseded)} superseded edge(s) retained + queryable, bitemporal)")

    print("\n--- honest summary ---")
    print("  Even:    write-path both call the LLM to extract; read retrieval deterministic for both.")
    print("  Mem0 +:  far more mature, bigger ecosystem, ~3 lines with OpenAI defaults.")
    print("  Prism +: deterministic *rendered* answers (cached, byte-identical), and built-in")
    print("           bitemporal time-travel/audit that Mem0 OSS charges for on the Platform.")


if __name__ == "__main__":
    main()
