"""PrismCortex quickstart — problem-first memory loop.

Runs out of the box with **zero external API keys** (rule-based extractor/renderer).
Pass ``GEMINI_API_KEY`` (or ``GOOGLE_API_KEY``) to use real Gemini extraction instead.

    python examples/quickstart.py
    GEMINI_API_KEY=... python examples/quickstart.py
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from prismcortex.adapters.reference import (
    DurableCache,
    HashingProjector,
    InMemoryGraphStore,
    InProcessMesh,
    InProcessResonance,
    ListStaging,
)
from prismcortex.engine import Memory
from prismcortex.models import (
    ExtractedEntity,
    ExtractedGist,
    ExtractedRelation,
    Subgraph,
)


class _RuleLLM:
    """Minimal extractor/renderer so the demo needs no network and no API key."""

    model_id = "quickstart-rules"

    def extract(self, text: str, context: Subgraph) -> ExtractedGist:
        t = text.strip()
        lower = t.lower()
        entities: list[ExtractedEntity] = []
        relations: list[ExtractedRelation] = []
        is_correction = any(w in lower for w in ("correction", "updated", "now ", "actually"))

        # CA leave policy
        m = re.search(r"parental leave.*?(\d+)\s*weeks?", lower)
        if m or ("leave" in lower and "week" in lower):
            weeks = m.group(1) if m else re.search(r"(\d+)\s*weeks?", lower)
            weeks = weeks if isinstance(weeks, str) else (weeks.group(1) if weeks else "12")
            entities = [
                ExtractedEntity(label="CA parental leave", kind="policy"),
                ExtractedEntity(label=f"{weeks} weeks", kind="value"),
            ]
            relations = [
                ExtractedRelation(src="CA parental leave", dst=f"{weeks} weeks", relation="is"),
            ]
            return ExtractedGist(
                entities=entities,
                relations=relations,
                is_correction=is_correction,
                notes="leave policy",
            )

        # Deploy budget — keep commas in the value label for readability
        m = re.search(r"\$\s*([\d,]+)", t)
        if m is None:
            m = re.search(r"budget.*?([\d,]+)", lower)
        if "budget" in lower and m:
            raw = m.group(1).replace(",", "")
            amount = f"${int(raw):,}"
            entities = [
                ExtractedEntity(label="deploy budget", kind="metric"),
                ExtractedEntity(label=amount, kind="value"),
            ]
            relations = [
                ExtractedRelation(src="deploy budget", dst=amount, relation="is"),
            ]
            return ExtractedGist(
                entities=entities,
                relations=relations,
                is_correction=is_correction,
                notes="budget",
            )

        # Region / DB
        if "postgres" in lower or "database" in lower:
            region = "us-east-1"
            rm = re.search(r"(us-[a-z]+-\d)", lower)
            if rm:
                region = rm.group(1)
            entities = [
                ExtractedEntity(label="primary database", kind="system"),
                ExtractedEntity(label="Postgres", kind="value"),
                ExtractedEntity(label=region, kind="region"),
            ]
            relations = [
                ExtractedRelation(src="primary database", dst="Postgres", relation="is"),
                ExtractedRelation(src="primary database", dst=region, relation="hosted_in"),
            ]
            return ExtractedGist(entities=entities, relations=relations, notes="database")

        return ExtractedGist(notes="no pattern matched")

    def render(self, query: str, subgraph: Subgraph) -> str:
        labels = {n.id: n.label for n in subgraph.nodes}
        qtokens = set(re.findall(r"[a-z0-9$]+", query.lower())) - {
            "what", "is", "our", "my", "the", "a", "an", "and", "do", "we", "which",
        }
        scored: list[tuple[int, str]] = []
        for e in subgraph.edges:
            if not e.is_current:
                continue
            src = labels.get(e.src, e.src)
            dst = labels.get(e.dst, e.dst)
            line = f"{src} {e.relation} {dst}"
            ltokens = set(re.findall(r"[a-z0-9$]+", line.lower()))
            scored.append((len(qtokens & ltokens), line))
        scored.sort(key=lambda x: (-x[0], x[1]))
        # Prefer query-overlapping facts; fall back to all current edges.
        lines = [line for score, line in scored if score > 0] or [line for _, line in scored]
        if not lines:
            return "No current facts in memory for that query."
        return "; ".join(lines) + "."


def _build_memory(*, cache_path: str) -> Memory:
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        from prismcortex import reference_memory

        print("Using Gemini extractor/renderer (GEMINI_API_KEY set).\n")
        return reference_memory(cache_path=cache_path)

    print("Using zero-deps rule extractor (set GEMINI_API_KEY for real LLM).\n")
    llm = _RuleLLM()
    return Memory(
        projector=HashingProjector(),
        extractor=llm,
        renderer=llm,
        store=InMemoryGraphStore(),
        resonance=InProcessResonance(),
        cache=DurableCache(path=cache_path),
        mesh=InProcessMesh(),
        staging=ListStaging(),
        tenant_id="enterprise_client_1",
    )


def main() -> None:
    cache_path = Path(".prismcortex_cache") / "quickstart.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    # Fresh demo cache so prior runs do not short-circuit digests.
    if cache_path.exists():
        cache_path.unlink()
    mem = _build_memory(cache_path=str(cache_path))

    print("=== 1) Digest turns (salience skips chit-chat) ===")
    for turn in [
        "California parental leave is 12 weeks.",
        "ok thanks",
        "My production deploy budget is $40,000.",
        "Primary database is Postgres, hosted in us-east-1.",
    ]:
        r = mem.digest(turn)
        print(f"  {r.outcome.value:11} band={r.band.value:9}  {turn[:56]!r}")

    print("\n=== 2) Consolidate staged facts (sleep) ===")
    consolidated = mem.sleep()
    print(f"  sleep() consolidated {consolidated} staged delta(s)")

    print("\n=== 3) Recall consolidated context ===")
    for q in [
        "What is our CA leave policy?",
        "What is my deploy budget?",
        "Which database and region do we use?",
    ]:
        hit = mem.recall(q)
        print(f"  Q: {q}")
        print(f"  A: {hit.answer}")
        print(f"     cache_hit={hit.cache_hit}  version={hit.version}  edges={len(hit.edge_ids)}")

    print("\n=== 4) Byte-identical replay ===")
    q = "What is my deploy budget?"
    a1, a2 = mem.recall(q), mem.recall(q)
    print(f"  identical={a1.answer == a2.answer}  second_cache_hit={a2.cache_hit}")

    print("\n=== 5) Correction + history retained ===")
    mem.digest("Correction: my deploy budget is now $55,000.")
    after = mem.recall(q)
    print(f"  A: {after.answer}")
    superseded = [e for e in mem.store.all_edges() if e.valid_to is not None]
    print(f"  superseded edges kept for time-travel: {len(superseded)}")

    expl = mem.explain("What is my deploy budget?")
    print("\n=== 6) Evidence trail ===")
    for ev in expl.evidence:
        prior = f" (was {ev.prior_value})" if ev.prior_value else ""
        print(f"  - {ev.fact}{prior}  conf={ev.confidence}")


if __name__ == "__main__":
    main()
