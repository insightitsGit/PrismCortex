#!/usr/bin/env bash
# Deploy the already-built image as 2 containers (server + driver), run the benchmark,
# capture logs + results. No rebuild. Not `set -e`: a transient az hiccup must not abort
# log capture. Gemini key is sourced from .env and passed as a SECURE env var.
set -uo pipefail
export PYTHONIOENCODING=utf-8
export MSYS_NO_PATHCONV=1   # stop Git Bash mangling /data into a Windows path
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
: "${GEMINI_API_KEY:?Set GEMINI_API_KEY in .env}"
: "${PRISMCORTEX_API_KEY:?Set PRISMCORTEX_API_KEY in .env (server auth)}"

RG=prismcortex-rg; ACR=prismcortexd7a6d0; IMG=prismcortex:bench
SRV=prismcortex-server; DRV=prismcortex-driver; DNS=prismcortex-srv-d7a6d0
BACKEND="${BACKEND:-prism}"   # prism = full PrismLang/PrismResonance stack; lite = hashing embeddings
MODEL="${PRISMCORTEX_MODEL:-gemini-2.5-flash@ga1}"  # @epoch pin (part of cache key)

LOGIN=$(az acr show -n "$ACR" -g "$RG" --query loginServer -o tsv)
AUSER=$(az acr credential show -n "$ACR" --query username -o tsv)
APASS=$(az acr credential show -n "$ACR" --query 'passwords[0].value' -o tsv)

echo "==> cleaning any prior container groups"
az container delete -g "$RG" -n "$SRV" --yes >/dev/null 2>&1 || true
az container delete -g "$RG" -n "$DRV" --yes >/dev/null 2>&1 || true

echo "==> deploy SERVER (public :8080)"
az container create -g "$RG" -n "$SRV" --image "$LOGIN/$IMG" \
  --registry-login-server "$LOGIN" --registry-username "$AUSER" --registry-password "$APASS" \
  --cpu 2 --memory 4 --os-type Linux --restart-policy Never \
  --ip-address Public --ports 8080 --dns-name-label "$DNS" \
  --environment-variables ROLE=server PRISMCORTEX_DATA=/data "PRISMCORTEX_BACKEND=$BACKEND" "PRISMCORTEX_MODEL=$MODEL" \
  --secure-environment-variables GEMINI_API_KEY="$GEMINI_API_KEY" PRISMCORTEX_API_KEY="$PRISMCORTEX_API_KEY" -o none
FQDN=$(az container show -g "$RG" -n "$SRV" --query ipAddress.fqdn -o tsv)
echo "    server: http://$FQDN:8080"

echo "==> deploy DRIVER (same region/zone)"
az container create -g "$RG" -n "$DRV" --image "$LOGIN/$IMG" \
  --registry-login-server "$LOGIN" --registry-username "$AUSER" --registry-password "$APASS" \
  --cpu 1 --memory 1.0 --os-type Linux --restart-policy Never \
  --environment-variables ROLE=driver SERVER_URL="http://$FQDN:8080" PRISMCORTEX_DATA=/data \
  --secure-environment-variables PRISMCORTEX_API_KEY="$PRISMCORTEX_API_KEY" -o none

echo "==> waiting for driver to finish"
for i in $(seq 1 100); do
  ST=$(az container show -g "$RG" -n "$DRV" --query 'containers[0].instanceView.currentState.state' -o tsv 2>/dev/null || echo "")
  echo "    [$i] driver: ${ST:-pending}"
  [ "$ST" = "Terminated" ] && break
  sleep 12
done

mkdir -p benchmarks/results
az container logs -g "$RG" -n "$DRV" > benchmarks/results/driver.log 2>&1 || true
az container logs -g "$RG" -n "$SRV" > benchmarks/results/server.log 2>&1 || true
awk '/RESULTS_JSON_BEGIN/{f=1;next}/RESULTS_JSON_END/{f=0}f' benchmarks/results/driver.log > benchmarks/results/results.json || true
echo "==> CAPTURED -> benchmarks/results/{driver.log,server.log,results.json}"
