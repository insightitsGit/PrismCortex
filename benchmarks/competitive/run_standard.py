#!/usr/bin/env python3
"""Run LoCoMo or LongMemEval with PrismCortex as the memory backend.

Uses prompts, datasets, and judge methodology from mem0ai/memory-benchmarks
(https://github.com/mem0ai/memory-benchmarks) with Mem0Client replaced by
PrismCortexClient and OpenAI replaced by Gemini.

Setup:
  bash scripts/setup_bench_vendor.sh
  pip install -e ".[bench,competitive]"
  GEMINI_API_KEY=... python benchmarks/competitive/run_standard.py locomo --project-name pc-smoke \\
      --max-conversations 1 --max-questions 10

Full runs (expensive — many Gemini extraction calls during ingest):
  python benchmarks/competitive/run_standard.py locomo --project-name pc-locomo-full
  python benchmarks/competitive/run_standard.py longmemeval --project-name pc-lme-full --all-questions
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDOR = REPO_ROOT / ".bench_vendor" / "memory-benchmarks"
OUT_DIR = REPO_ROOT / "benchmarks" / "results" / "competitive"


def _load_adapter(name: str, filename: str):
    path = REPO_ROOT / "benchmarks" / "competitive" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ensure_vendor() -> None:
    if not VENDOR.is_dir():
        print("Missing vendor checkout. Run: bash scripts/setup_bench_vendor.sh", file=sys.stderr)
        sys.exit(1)


def _patch_and_import():
    _ensure_vendor()
    sys.path.insert(0, str(VENDOR))
    sys.path.insert(0, str(REPO_ROOT))

    pc_mod = _load_adapter("prismcortex_client", "prismcortex_client.py")
    gem_mod = _load_adapter("gemini_llm", "gemini_llm.py")

    import benchmarks.common.llm_client as llm_mod  # noqa: WPS433
    import benchmarks.common.mem0_client as mem0_mod  # noqa: WPS433

    mem0_mod.Mem0Client = pc_mod.PrismCortexClient
    llm_mod.LLMClient = gem_mod.GeminiLLMClient


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    benchmark = sys.argv[1]
    if benchmark not in ("locomo", "longmemeval"):
        print(f"Unknown benchmark: {benchmark}. Use locomo or longmemeval.", file=sys.stderr)
        sys.exit(1)

    forwarded = sys.argv[2:]
    if "--answerer-model" not in forwarded:
        forwarded.extend(["--answerer-model", "gemini-2.5-flash"])
    if "--judge-model" not in forwarded:
        forwarded.extend(["--judge-model", "gemini-2.5-flash"])

    _patch_and_import()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if benchmark == "locomo":
        import benchmarks.locomo.run as locomo_run  # noqa: WPS433

        sys.argv = ["locomo.run", *forwarded]
        locomo_run.main()
    else:
        import benchmarks.longmemeval.run as lme_run  # noqa: WPS433

        sys.argv = ["longmemeval.run", *forwarded]
        lme_run.main()


if __name__ == "__main__":
    main()
