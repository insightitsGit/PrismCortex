"""Messy-data benchmark — extraction drift without calling Gemini.

Simulates the failure modes seen in adversarial runs: subject paraphrase, relation
wording drift, and crowded-graph recall. Uses scripted gists so results are stable
in CI; run adversarial_bench.py for the real-Gemini version.

Run:  python benchmarks/messy_bench.py
      pytest tests/test_graph_engine.py -k "canonical or crowded or value_conflict"
"""
from __future__ import annotations

import sys
import tempfile

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
    Band,
    ExtractedEntity,
    ExtractedGist,
    ExtractedRelation,
    Provenance,
    Subgraph,
)


class _Render:
    model_id = "messy-bench"

    def render(self, query: str, subgraph) -> str:
        labels = {n.id: n.label for n in subgraph.nodes}
        parts = []
        for e in subgraph.edges:
            if e.valid_to is not None:
                continue
            parts.append(f"{labels.get(e.src, e.src)} {e.relation} {labels.get(e.dst, e.dst)}")
        return "; ".join(parts) if parts else "I do not have that information yet."


class _ScriptedExtractor:
    model_id = "scripted"

    def __init__(self, gists: list[ExtractedGist]) -> None:
        self._gists = list(gists)
        self._i = 0

    def extract(self, text: str, context: Subgraph) -> ExtractedGist:
        if self._i >= len(self._gists):
            return ExtractedGist()
        g = self._gists[self._i]
        self._i += 1
        return g


def _mem(extractor: _ScriptedExtractor) -> Memory:
    return Memory(
        projector=HashingProjector(dim=128),
        extractor=extractor,
        renderer=_Render(),
        store=InMemoryGraphStore(),
        resonance=InProcessResonance(),
        cache=DurableCache(),
        mesh=InProcessMesh(),
        staging=ListStaging(),
        k=6,
    )


def main() -> None:
    results: list[tuple[str, bool]] = []

    # 1) Pollute graph (like adversarial probe 1), then ingest launch with subject drift.
    ext = _ScriptedExtractor([
        ExtractedGist(
            entities=[ExtractedEntity(label="Acme Corp"), ExtractedEntity(label="Boston")],
            relations=[ExtractedRelation(src="Acme Corp", dst="Boston", relation="headquartered in")],
        ),
        ExtractedGist(
            entities=[ExtractedEntity(label="Acme Health"), ExtractedEntity(label="Denver")],
            relations=[ExtractedRelation(src="Acme Health", dst="Denver", relation="headquartered in")],
        ),
        ExtractedGist(
            entities=[ExtractedEntity(label="product launch"), ExtractedEntity(label="March")],
            relations=[ExtractedRelation(src="product launch", dst="March", relation="is scheduled for")],
        ),
        ExtractedGist(
            entities=[ExtractedEntity(label="launch"), ExtractedEntity(label="June")],
            relations=[ExtractedRelation(src="launch", dst="June", relation="scheduled for")],
        ),
    ])
    m = _mem(ext)
    for i in range(4):
        m.digest(f"ingest turn {i} with durable team facts for memory")
    m.sleep()
    ans = m.recall("When is the product launch?").answer.lower()
    ok = "june" in ans and "march" not in ans.split("june")[0]
    results.append(("contradiction under crowded graph + subject drift", ok))
    superseded = sum(1 for e in m.store.all_edges() if e.valid_to is not None)
    results.append(("history retained after consolidation", superseded >= 1))

    # 2) Budget paraphrase: "the deploy budget" -> same subject as "deploy budget".
    ext2 = _ScriptedExtractor([
        ExtractedGist(
            entities=[ExtractedEntity(label="deploy budget"), ExtractedEntity(label="$40,000")],
            relations=[ExtractedRelation(src="deploy budget", dst="$40,000", relation="is")],
        ),
        ExtractedGist(
            entities=[ExtractedEntity(label="the deploy budget"), ExtractedEntity(label="$55,000")],
            relations=[ExtractedRelation(src="the deploy budget", dst="$55,000", relation="is")],
        ),
    ])
    m2 = _mem(ext2)
    m2.digest("first budget fact from planning meeting")
    m2.digest("updated budget figure from finance review")
    m2.sleep()
    ans2 = m2.recall("deploy budget?").answer
    results.append(("canonical subject resolves paraphrase", "$55,000" in ans2 or "55" in ans2))

    print("Messy-data probes (scripted extraction drift):\n")
    passed = 0
    for name, ok in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        passed += int(ok)
    print(f"\nMESSY-DATA: {passed}/{len(results)} passed")
    if passed < len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
