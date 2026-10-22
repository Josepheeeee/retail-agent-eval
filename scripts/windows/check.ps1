# Offline checks: tests, compile, and fixture demo. No live API call.
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Run scripts\windows\setup.ps1 first" }
& $py -m pytest -q
& $py -m compileall -q src scripts
& $py -m retail_eval.run doctor
& $py -m retail_eval.run demo
Write-Host "Offline checks complete. Demo artifacts are fixtures, not benchmark results."
