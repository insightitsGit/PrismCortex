"""Correctness metrics separate from determinism (no Gemini required for scripted path)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    print("=== Correctness bench (determinism != correctness) ===\n")
    root = Path(__file__).resolve().parent.parent
    r = subprocess.run([sys.executable, str(root / "benchmarks" / "messy_bench.py")], cwd=str(root))
    if r.returncode:
        sys.exit(r.returncode)
    print("\nCorrectness probes: PASS (scripted extraction drift)")


if __name__ == "__main__":
    main()
