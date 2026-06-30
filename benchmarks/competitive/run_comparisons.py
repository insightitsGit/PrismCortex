"""Run head-to-head comparisons and write JSON artifacts."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RESULTS = Path(__file__).resolve().parents[1] / "results" / "competitive"


def _run(script: str, env: dict | None = None) -> int:
    root = Path(__file__).resolve().parents[2]
    cmd = [sys.executable, str(root / "benchmarks" / script)]
    merged = os.environ.copy()
    if env:
        merged.update(env)
    print(f"\n>>> {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=str(root), env=merged)


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    summary: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "runs": [],
    }

    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        for name in ("vs_mem0.py", "vs_zep.py"):
            rc = _run(name)
            summary["runs"].append({"script": name, "exit_code": rc})
    else:
        print("Skip vs_mem0/vs_zep — GEMINI_API_KEY not set")

    if os.environ.get("RUN_STANDARD_BENCH") == "1":
        vendor = Path(__file__).resolve().parents[2] / ".bench_vendor" / "memory-benchmarks"
        if vendor.is_dir():
            rc = _run(
                "competitive/run_standard.py",
            )
            # invoked differently
        else:
            print("Skip standard benchmarks — run scripts/setup_bench_vendor.sh first")

    out = RESULTS / "comparison_summary.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSummary -> {out}")


if __name__ == "__main__":
    main()
