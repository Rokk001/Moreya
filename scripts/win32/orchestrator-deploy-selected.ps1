# ODP deployment entry point shared by queued worktrees, including worktrees with legacy probe scripts.
# Freeze the outgoing data commit and successful baseline before deploying; publish success only after all probes pass.
param(
    [Parameter(Mandatory = $true)][string]$Counter,
    [Parameter(Mandatory = $true)][string]$DeployScript,
    [string]$Worktree = (Get-Location).Path,
    [switch]$FullCampaign,
    [switch]$SelectionOnly
)
$ErrorActionPreference = 'Stop'
$wt = (Resolve-Path -LiteralPath $Worktree).Path
$scripts = Split-Path -Parent $PSScriptRoot
$common = (& git -C $wt rev-parse --path-format=absolute --git-common-dir).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve shared deployment state' }
$repo = Split-Path -Parent $common
$receipt = Join-Path $common 'odp-deploy-success.json'
$tip = (& git -C $wt rev-parse --verify 'HEAD^{commit}').Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve outgoing integration commit' }
# The selected data belongs to the built worktree, not a remote ref that another push can advance.
& git -C $wt merge-base --is-ancestor $tip origin/integration/all
if ($LASTEXITCODE -ne 0) { throw 'Outgoing worktree commit is not contained in integration/all' }
$run = (Get-Content -LiteralPath "$wt\out\orch-run.txt" | Select-Object -First 1).Trim()
$n = (Get-Content -LiteralPath "$wt\out\build-number-$run.txt" | Select-Object -First 1).Trim()
if ($n -notmatch '^\d+$' -or $run -notmatch '^[\w-]+$') { throw 'Invalid build metadata' }
$manifest = "$wt\out\deploy-selection-$run.json"
$selectionArgs = @('--repo', $repo, '--tip', $tip, '--receipt', $receipt, '--output', $manifest)
if ($FullCampaign) { $selectionArgs += '--all-campaign' }
& python "$scripts\deploy-level-selection.py" @selectionArgs
if ($LASTEXITCODE -ne 0) { throw 'Deployment selection failed; no deployment or map test was started' }
if ($SelectionOnly) { exit 0 }
# The shared deployment script rejects every legacy caller without this verified selection manifest.
& powershell -NoProfile -File $DeployScript -ExeDir "$wt\build\windows" -SelectionFile $manifest
if ($LASTEXITCODE -ne 0) { throw "Deploy failed (exit $LASTEXITCODE)" }
$data = Join-Path $repo 'build\current-worktree'
$actual = (& git -C $data rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $actual -ne $tip) { throw 'Deployed data does not match selected commit' }
$exe = Join-Path $repo 'build\windows\opendungeons-plus.exe'
& python "$scripts\run-campaign-load-tests.py" --repo $data --deployment-selection $manifest --executable $exe --output "$wt\out\deployed-load-$run"
if ($LASTEXITCODE -ne 0) { throw "Load test with the deployed exe failed (exit $LASTEXITCODE)" }
Set-Content -Encoding ascii -LiteralPath $Counter -Value $n
& python "$scripts\deploy-level-selection.py" @selectionArgs --record-success --executable $exe
if ($LASTEXITCODE -ne 0) { throw 'Could not record successful deployment; comparison baseline was not advanced' }
Write-Output "deployed build $n; verified data commit $tip"
exit 0
