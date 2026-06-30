# PrismCortex — run competitive benchmarks (PowerShell)
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $Root) { $Root = (Get-Location).Path }
$Target = Join-Path $Root ".bench_vendor\memory-benchmarks"
if (Test-Path (Join-Path $Target ".git")) {
    Write-Host "Updating memory-benchmarks..."
    git -C $Target pull --ff-only
} else {
    New-Item -ItemType Directory -Force -Path (Join-Path $Root ".bench_vendor") | Out-Null
    git clone --depth 1 https://github.com/mem0ai/memory-benchmarks.git $Target
}
Write-Host "Vendor ready: $Target"
pip install -q aiohttp aiolimiter tqdm python-dotenv 2>$null
