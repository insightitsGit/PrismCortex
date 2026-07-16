#!/usr/bin/env bash
# Clone mem0ai/memory-benchmarks for LoCoMo / LongMemEval runners (not vendored in git).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$ROOT/.bench_vendor/memory-benchmarks"
if [[ -d "$TARGET/.git" ]]; then
  echo "Updating memory-benchmarks..."
  git -C "$TARGET" pull --ff-only
else
  mkdir -p "$ROOT/.bench_vendor"
  git clone --depth 1 https://github.com/mem0ai/memory-benchmarks.git "$TARGET"
fi
echo "Vendor ready: $TARGET"
pip install -q aiohttp aiolimiter tqdm python-dotenv 2>/dev/null || true
