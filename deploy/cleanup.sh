#!/usr/bin/env bash
# Tear down the entire benchmark: deletes the resource group (ACR + both container
# groups) so nothing keeps billing. Isolated RG => clean, total teardown.
set -euo pipefail
RG="${RG:-prismcortex-rg}"
echo "deleting resource group $RG (ACR + container groups) ..."
az group delete -n "$RG" --yes --no-wait
echo "delete requested (running in background)."
