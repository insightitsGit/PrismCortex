#!/usr/bin/env python3
"""Generate a CycloneDX-style SBOM JSON from installed package metadata."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    out = Path("benchmarks/results/sbom.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        capture_output=True,
        text=True,
        check=True,
    )
    components = []
    for line in proc.stdout.splitlines():
        if "==" in line:
            name, version = line.split("==", 1)
            components.append({"name": name, "version": version, "type": "library"})
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "version": 1,
        "metadata": {"timestamp": datetime.now(timezone.utc).isoformat(), "component": {"name": "prismcortex", "version": "0.2.0"}},
        "components": components,
    }
    out.write_text(json.dumps(sbom, indent=2), encoding="utf-8")
    print(f"Wrote {out} ({len(components)} components)")


if __name__ == "__main__":
    main()
