#!/bin/sh
set -e
ROLE="${ROLE:-server}"

if [ "$ROLE" = "server" ]; then
  HOST="${UVICORN_HOST:-0.0.0.0}"
  PORT="${PORT:-8080}"
  KEEP_ALIVE="${UVICORN_KEEP_ALIVE:-30}"
  LIMIT="${UVICORN_LIMIT_CONCURRENCY:-256}"
  echo "[entrypoint] starting PrismCortex memory service on ${HOST}:${PORT} (limit-concurrency=${LIMIT})"
  exec uvicorn prismcortex.server:app \
    --host "$HOST" \
    --port "$PORT" \
    --timeout-keep-alive "$KEEP_ALIVE" \
    --limit-concurrency "$LIMIT"
elif [ "$ROLE" = "driver" ]; then
  echo "[entrypoint] starting benchmark driver -> ${SERVER_URL:-http://localhost:8080}"
  exec python benchmarks/driver.py
else
  echo "[entrypoint] unknown ROLE='$ROLE' (expected server|driver)"
  exit 1
fi
