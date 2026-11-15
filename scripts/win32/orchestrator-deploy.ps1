# HaiveQueen Orchestrator, Deploy step of ODP. Runs in the plan worktree after the push: deploy of the release build of this worktree,
# load test with the deployed exe, then the build number of this build is written to the counter file. Exit 0 = green.
# -Counter: file with the last deployed build number. -DeployScript: path of deploy-current.ps1.
# -GameWaitSeconds: bounded wait for the owner to close the game before deployment (default 30 minutes).
param(
    [Parameter(Mandatory = $true)][string]$Counter,
    [Parameter(Mandatory = $true)][string]$DeployScript,
    [ValidateRange(0, 86400)][int]$GameWaitSeconds = 1800
)
# Native errors and real child exit codes determine the outcome, never log text.
$ErrorActionPreference = 'Stop'
$wt = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
# One shared OS lock covers the normal deploy, deployed probes and counter update.
# The helper loads Get-FileHash from the child PowerShell installation even if its module search path is incomplete.
# The deployed exe is in build\windows of the main checkout, found through the shared git directory of this worktree.
& python -I "$wt\scripts\odp_deployment.py" deploy --repo $wt --counter $Counter --deploy-script $DeployScript --game-wait-seconds $GameWaitSeconds
exit $LASTEXITCODE
