#!/usr/bin/env bash
# Cloud-build v0.2 image in ACR, then run the 2-container Azure benchmark.
set -euo pipefail
export PYTHONIOENCODING=utf-8
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")/.."

RG=prismcortex-rg
ACR=prismcortexd7a6d0
IMG=prismcortex:bench
LOG=benchmarks/results/acr_build_v02.log

mkdir -p benchmarks/results
echo "==> [1/2] ACR cloud build (v0.2) — log: $LOG"
echo "    started $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee "$LOG"
az acr build -r "$ACR" -g "$RG" -t "$IMG" . 2>&1 | tee -a "$LOG"
echo "    finished $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG"

echo "==> [2/2] deploy + benchmark (prism backend)"
BACKEND=prism bash deploy/run_only.sh 2>&1 | tee benchmarks/results/deploy_v02.log
