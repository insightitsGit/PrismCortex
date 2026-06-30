# Publish prismcortex to PyPI (https://pypi.org/project/prismcortex/)
#
# Prerequisites:
#   1. PyPI account with project name "prismcortex" (first upload claims the name)
#   2. API token: https://pypi.org/manage/account/token/
#
# Usage (PowerShell — do NOT commit the token):
#   $env:PYPI_API_TOKEN = "pypi-..."
#   .\scripts\publish_pypi.ps1
#
# Or use trusted publishing via GitHub Release (.github/workflows/publish.yml).

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Get-PypiToken {
    if ($env:PYPI_API_TOKEN) { return $env:PYPI_API_TOKEN }
    if ($env:TWINE_PASSWORD) { return $env:TWINE_PASSWORD }
    $envFile = Join-Path $Root ".env"
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            if ($_ -match '^\s*PYPI_API_TOKEN=(.+)$') {
                return $matches[1].Trim().Trim('"').Trim("'")
            }
        }
    }
    return $null
}

$token = Get-PypiToken
if (-not $token) {
    Write-Error "Set PYPI_API_TOKEN in .env or `$env:PYPI_API_TOKEN before running."
}

Write-Host "==> Running tests..."
python -m pytest tests/ -q --tb=line
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Building sdist + wheel..."
if (Test-Path dist) { Remove-Item -Recurse -Force dist }
if (Test-Path build) { Remove-Item -Recurse -Force build }
python -m pip install -q build twine
python -m build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> twine check..."
python -m twine check dist/*
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Uploading to PyPI..."
$env:TWINE_USERNAME = "__token__"
$env:TWINE_PASSWORD = $token
python -m twine upload dist/*
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Published. Verify: pip install prismcortex==0.2.1"
Write-Host "PyPI: https://pypi.org/project/prismcortex/"
