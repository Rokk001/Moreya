# HaiveQueen Orchestrator, Deploy step of ODP. Runs in the plan worktree after the push: deploy of the release build of this worktree,
# load test with the deployed exe, then the build number of this build is written to the counter file. Exit 0 = green.
# -Counter: file with the last deployed build number. -DeployScript: path of deploy-current.ps1.
param(
    [Parameter(Mandatory = $true)][string]$Counter,
    [Parameter(Mandatory = $true)][string]$DeployScript,
    [ValidateRange(0, 86400)][int]$GameWaitSeconds = 1800
)
# Native errors and real child exit codes determine the outcome, never log text.
$ErrorActionPreference = 'Stop'
$wt = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
# The selected entry point loads the child PowerShell utility module through DeployScript,
# resolves the deployed EXE through the shared Git directory and advances the build counter only after passing probes.
& powershell -NoProfile -File "$PSScriptRoot\orchestrator-deploy-selected.ps1" -Counter $Counter -DeployScript $DeployScript -Worktree $wt -GameWaitSeconds $GameWaitSeconds
exit $LASTEXITCODE
