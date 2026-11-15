# HaiveQueen Orchestrator, Deploy step of ODP. Runs in the plan worktree after the push: deploy of the release build of this worktree,
# load test with the deployed exe, then the build number of this build is written to the counter file. Exit 0 = green.
# -Counter: file with the last deployed build number. -DeployScript: path of deploy-current.ps1.
# -GameWaitSeconds: bounded wait for the owner to close the game before deployment (default 30 minutes).
param(
    [Parameter(Mandatory = $true)][string]$Counter,
    [Parameter(Mandatory = $true)][string]$DeployScript,
    [ValidateRange(0, 86400)][int]$GameWaitSeconds = 1800
)
$ErrorActionPreference = 'Continue'
$wt = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$run = Get-Content "$wt\out\orch-run.txt" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $run) { Write-Output 'no Build step of this worktree found (out\orch-run.txt missing)'; exit 1 }
$n = (Get-Content "$wt\out\build-number-$run.txt" | Select-Object -First 1).Trim()
# Load Get-FileHash from the child PowerShell installation even if its module search path is incomplete.
$deployScriptLiteral = $DeployScript.Replace("'", "''")
$exeDirLiteral = "$wt\build\windows".Replace("'", "''")
$waitScriptLiteral = (Join-Path $PSScriptRoot 'wait-game-exit.ps1').Replace("'", "''")
$deployCommand = @"
Import-Module (Join-Path `$PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
. '$waitScriptLiteral'
try { Wait-GameExit -TimeoutSeconds $GameWaitSeconds }
catch { Write-Error `$_; exit 1 }
& '$deployScriptLiteral' -ExeDir '$exeDirLiteral'
if (`$?) { exit 0 }
if (`$LASTEXITCODE) { exit `$LASTEXITCODE }
exit 1
"@
& powershell -NoProfile -Command $deployCommand
if ($LASTEXITCODE -ne 0) { Write-Output "deploy failed (exit $LASTEXITCODE)"; exit 1 }
# The deployed exe is in build\windows of the main checkout, found through the shared git directory of this worktree
$common = (& git -C $wt rev-parse --path-format=absolute --git-common-dir).Trim()
$exe = Join-Path (Split-Path -Parent ($common -replace '/', '\')) 'build\windows\opendungeons-plus.exe'
& python "$wt\scripts\run-campaign-load-tests.py" --executable $exe --output "$wt\out\deployed-load-$run"
if ($LASTEXITCODE -ne 0) { Write-Output "load test with the deployed exe failed (exit $LASTEXITCODE)"; exit 1 }
Set-Content -Encoding ascii $Counter $n
Write-Output "deployed build $n"
exit 0
