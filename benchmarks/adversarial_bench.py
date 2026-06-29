"""Adversarial benchmark — probes the hard cases a friendly demo hides.

Real Gemini, full prism stack. Each probe is designed to *try to break* the system:
similar-name over-merge, contradiction+history, distractor precision, and multi-hop
(the one we expect to be weak). Honest pass/fail; finding a failure is the point.

Run:  GEMINI_API_KEY=...  python benchmarks/adversarial_bench.py
"""
from __future__ import annotations

import os
import sys
import tempfile

if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
    sys.exit("Set GEMINI_API_KEY — adversarial probes use real Gemini, never mocked.")

from prismcortex.adapters.prism import prism_memory


def main() -> None:
    d = tempfile.mkdtemp()
    m = prism_memory(
        cache_db=os.path.join(d, "c.db"),
        resonance_state=os.path.join(d, "r.db"),
        resonance_onnx=os.path.join(d, "r.onnx"),
    )
    results = []

    def probe(name, ingest, query, check, do_sleep=False):
        for t in ingest:
            m.digest(t)
        if do_sleep:
            m.sleep()
        ans = m.recall(query).answer
        ok = check(ans.lower())
        results.append((name, ok))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}\n         Q: {query}\n         A: {ans[:72]!r}")

    print("Adversarial probes (real Gemini, full prism stack):\n")

    probe(
        "over-merge guard (similar names must stay distinct)",
        ["Acme Corp is headquartered in Boston.", "Acme Health is headquartered in Denver."],
        "Where is Acme Corp headquartered?",
        lambda a: "boston" in a and "denver" not in a,
    )
    probe(
        "contradiction + history (latest value wins)",
        ["The product launch is scheduled for March.", "The product launch is scheduled for June."],
        "When is the product launch?",
        lambda a: "june" in a,
        do_sleep=True,
    )
    probe(
        "distractor precision (pick 1 right of 6 similar)",
        ["The frontend team uses React.", "The backend team uses Go.",
         "The data team uses Spark.", "The mobile team uses Swift.",
         "The infra team uses Terraform.", "The ML team uses PyTorch."],
        "What does the data team use?",
        lambda a: "spark" in a,
    )
    probe(
        "multi-hop (person -> project -> database)",
        ["Sarah leads the Atlas project.", "The Atlas project runs on Postgres."],
        "What database does Sarah's project run on?",
        lambda a: "postgres" in a,
    )

    superseded = [e for e in m.store.all_edges() if e.valid_to is not None]
    print(f"\n  time-travel: {len(superseded)} superseded fact(s) retained for audit")
    passed = sum(1 for _, ok in results if ok)
    print(f"\nADVERSARIAL: {passed}/{len(results)} probes passed "
          f"(a fail here is a finding, not a bug to hide)")


if __name__ == "__main__":
    main()
