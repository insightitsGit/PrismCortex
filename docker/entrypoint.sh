#!/bin/sh
set -e
ROLE="${ROLE:-server}"

if [ "$ROLE" = "server" ]; then
  echo "[entrypoint] starting PrismCortex memory service on :${PORT:-8080}"
  exec uvicorn prismcortex.server:app --host 0.0.0.0 --port "${PORT:-8080}"
elif [ "$ROLE" = "driver" ]; then
  echo "[entrypoint] starting benchmark driver -> ${SERVER_URL:-http://localhost:8080}"
  exec python benchmarks/driver.py
else
  echo "[entrypoint] unknown ROLE='$ROLE' (expected server|driver)"
  exit 1
fi
