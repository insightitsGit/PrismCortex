"""PrismCortex quickstart — the whole memory loop in ~30 lines.

Needs a real Gemini key (extraction + rendering are real model calls, never mocked):
    GEMINI_API_KEY=...  python examples/quickstart.py
"""
from prismcortex import reference_memory

mem = reference_memory(cache_path=".prismcortex_cache/quickstart.json")

# 1) Digest a few turns. "ok thanks" is skipped by the salience gate (no LLM call).
for turn in [
    "My name is Amin and my production deploy budget is $40,000.",
    "ok thanks",
    "My primary database is Postgres, hosted in us-east-1.",
]:
    r = mem.digest(turn)
    print(f"digest: {r.outcome.value:11} band={r.band.value:9} {turn[:48]!r}")

# 2) Recall — deterministic, traceable.
q = "What is my deploy budget and which region is my database in?"
first = mem.recall(q)
print(f"\nQ: {q}\nA: {first.answer}")
print(f"   cache_hit={first.cache_hit}  facts={len(first.node_ids)} nodes / {len(first.edge_ids)} edges")

# 3) Replay the same question → byte-identical, served from cache, zero tokens.
second = mem.recall(q)
print(f"\nreplay: cache_hit={second.cache_hit}  identical={first.answer == second.answer}")

# 4) Correct a fact → fast-tracked. The graph changes, so the answer changes —
#    and the old fact stays on record for audit/time-travel.
mem.digest("Correction: my deploy budget is now $55,000.")
after = mem.recall(q)
print(f"\nafter correction:\nA: {after.answer}")
print(f"   answer changed: {after.answer != first.answer}")

invalidated = [e for e in mem.store.all_edges() if e.valid_to is not None]
print(f"   superseded facts kept for time-travel: {len(invalidated)}")
