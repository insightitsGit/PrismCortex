#!/usr/bin/env bash
# PrismCortex — real 2-container Azure benchmark.
#
#   Container A (server) = the full self-contained PrismCortex memory (PrismLib cache
#                          inside) exposed on :8080.
#   Container B (driver) = a second agent that connects over the network and benchmarks.
#
# Same region (eastus) => same-zone, real intra-region network. No external datastore.
# The Gemini key is read from .env (gitignored) and passed as a SECURE env var — it is
# never written to a command line literal, the transcript, or git.
set -euo pipefail

RG="${RG:-prismcortex-rg}"
LOC="${LOC:-eastus}"
ACR="${ACR:-prismcortexd7a6d0}"
IMG="prismcortex:bench"
SRV="prismcortex-server"
DRV="prismcortex-driver"
DNS="${DNS:-prismcortex-srv-d7a6d0}"

cd "$(dirname "$0")/.."
if [ -f .env ]; then set -a; . ./.env; set +a; fi
: "${GEMINI_API_KEY:?Set GEMINI_API_KEY in .env (gitignored) or the environment}"

echo "==> [1/6] resource group $RG ($LOC)"
az group create -n "$RG" -l "$LOC" -o none

echo "==> [2/6] container registry $ACR"
az acr create -n "$ACR" -g "$RG" --sku Basic --admin-enabled true -o none
LOGIN=$(az acr show -n "$ACR" -g "$RG" --query loginServer -o tsv)
USER=$(az acr credential show -n "$ACR" --query username -o tsv)
PASS=$(az acr credential show -n "$ACR" --query 'passwords[0].value' -o tsv)

echo "==> [3/6] cloud build image (no local docker)"
az acr build -r "$ACR" -t "$IMG" . -o none

echo "==> [4/6] deploy SERVER (public :8080, 4 vCPU / 8 GB)"
az container create -g "$RG" -n "$SRV" --image "$LOGIN/$IMG" \
  --registry-login-server "$LOGIN" --registry-username "$USER" --registry-password "$PASS" \
  --cpu 4 --memory 8 --os-type Linux --restart-policy Never \
  --ip-address Public --ports 8080 --dns-name-label "$DNS" \
  --environment-variables ROLE=server PRISMCORTEX_DATA=/data PRISMCORTEX_BACKEND=prism \
    PRISMCORTEX_USE_ANN=1 PRISMCORTEX_READ_POOL=64 PRISMCORTEX_MAX_CONCURRENT_DIGEST=16 \
    UVICORN_LIMIT_CONCURRENCY=256 \
  --secure-environment-variables GEMINI_API_KEY="$GEMINI_API_KEY" -o none
FQDN=$(az container show -g "$RG" -n "$SRV" --query ipAddress.fqdn -o tsv)
echo "    server: http://$FQDN:8080"

echo "==> [5/6] deploy DRIVER (same region/zone)"
az container create -g "$RG" -n "$DRV" --image "$LOGIN/$IMG" \
  --registry-login-server "$LOGIN" --registry-username "$USER" --registry-password "$PASS" \
  --cpu 1 --memory 1.0 --os-type Linux --restart-policy Never \
  --environment-variables ROLE=driver SERVER_URL="http://$FQDN:8080" PRISMCORTEX_DATA=/data -o none

echo "==> [6/6] waiting for driver to finish + capturing logs"
while :; do
  ST=$(az container show -g "$RG" -n "$DRV" --query 'containers[0].instanceView.currentState.state' -o tsv 2>/dev/null || echo "")
  echo "    driver state: ${ST:-pending}"
  [ "$ST" = "Terminated" ] && break
  sleep 10
done

mkdir -p benchmarks/results
az container logs -g "$RG" -n "$DRV" > benchmarks/results/driver.log 2>&1 || true
az container logs -g "$RG" -n "$SRV" > benchmarks/results/server.log 2>&1 || true
awk '/RESULTS_JSON_BEGIN/{f=1;next}/RESULTS_JSON_END/{f=0}f' benchmarks/results/driver.log > benchmarks/results/results.json || true
echo "==> saved benchmarks/results/{driver.log,server.log,results.json}"
echo "==> tear down with: deploy/cleanup.sh"
