# HaiveQueen Orchestrator, Build step of ODP. Runs in the plan worktree: build number, configure, Release build, then all check scripts and the load test (run-checks.py).
# Parallel value, compiler jobs and minimum free RAM come from the HaiveQueen build settings (BUILD_PARALLEL, BUILD_JOBS, BUILD_MIN_FREE_RAM_GB).
# -Counter: file with the last deployed build number (only read here, the Deploy step writes it). -Base: the last deployed state. -Checks: path of run-checks.py.
param(
    [Parameter(Mandatory = $true)][string]$Counter,
    [Parameter(Mandatory = $true)][string]$Base,
    [Parameter(Mandatory = $true)][string]$Checks
)
# Native stderr must not end the script; only the exit codes decide
$ErrorActionPreference = 'Continue'
$wt = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
# The versioned ODP runner owns the journal; the historical -Checks argument remains accepted for existing HQ commands.
$Checks = Join-Path $wt 'scripts\run-checks.py'
New-Item -ItemType Directory -Force "$wt\out" | Out-Null
$run = 'orch-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
$loadBase = $Base
$preflightLog = "$wt\out\preflight-$run.log"
$start = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$stages = [ordered]@{
    'build:preflight' = @{ exit = 125; kind = 'prerequisite'; output = 'Build preflight did not complete' }
    'build:configure' = @{ exit = 125; kind = 'prerequisite'; output = 'Configure not executed because preflight failed' }
    'build:release' = @{ exit = 125; kind = 'prerequisite'; output = 'Release build not executed because configuration failed' }
}
try {
# Services may have started before the user-level asset source setting was added.
if (-not $env:ODP_ASSETS_SRC) { $env:ODP_ASSETS_SRC = [Environment]::GetEnvironmentVariable('ODP_ASSETS_SRC', 'User') }
Set-Content -Encoding ascii "$wt\out\orch-run.txt" $run
# Freeze the integration reference before Push updates origin/integration/all.
& python "$wt\scripts\run-campaign-load-tests.py" --repo $wt --capture-base $Base --output "$wt\out\load-base-$run.json" 2>&1 | Tee-Object -FilePath $preflightLog
if ($LASTEXITCODE -ne 0) { throw 'could not capture integration load-test base' }
$loadBase = (Get-Content -Raw "$wt\out\load-base-$run.json" | ConvertFrom-Json).base
# The compiler job count of HaiveQueen (BUILD_JOBS) becomes the /MP job count of the project (BUILD_MP_JOBS, read by windows-paths.ps1)
if ($env:BUILD_JOBS -and -not $env:BUILD_MP_JOBS) { $env:BUILD_MP_JOBS = $env:BUILD_JOBS }
. (Join-Path $PSScriptRoot 'windows-paths.ps1')
$n = [int](& python -I "$wt\scripts\next-build-number.py" --counter $Counter --base $Base 2>&1 | Tee-Object -FilePath $preflightLog -Append)
if ($LASTEXITCODE -ne 0) { throw "build number failed (exit $LASTEXITCODE)" }
Set-Content -Encoding ascii "$wt\out\build-number-$run.txt" $n
$stages['build:preflight'] = @{ exit = 0; log = $preflightLog }
Write-Output "configure started: $run"
& powershell -NoProfile -File "$PSScriptRoot\configure-windows-prereqs.ps1" -BuildNumber $n *>&1 | Tee-Object -FilePath "$wt\out\configure-$run.log"
$configureCode = $LASTEXITCODE
$stages['build:configure'] = @{ exit = $configureCode; log = "$wt\out\configure-$run.log" }
if ($configureCode -ne 0) { throw "configure failed (exit $configureCode)" }
$parallel = if ($env:BUILD_PARALLEL) { [int]$env:BUILD_PARALLEL } else { 1 }
# Force a fresh link even when an integration retry has no changed source files.
# The load test requires an executable produced after this run's build start.
$exe = Join-Path $wt 'build\windows\opendungeons-plus.exe'
if (Test-Path -LiteralPath $exe) { Remove-Item -LiteralPath $exe -Force -ErrorAction Stop }
# Epoch time right before the build; run-checks.py needs it as --build-start
$start = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
Write-Output "build started: $run"
& $taskCmakeExe --build "$wt\build\windows" --config Release --target opendungeons-plus --parallel $parallel *>&1 | Tee-Object -FilePath "$wt\out\build-$run.log"
$code = $LASTEXITCODE
Set-Content -Encoding ascii "$wt\out\build-exit-$run.txt" $code
$stages['build:release'] = @{ exit = $code; log = "$wt\out\build-$run.log" }
if ($code -ne 0) { throw "build failed (exit $code)" }
} catch {
    Write-Output "Build prerequisite failure: $_"
    if ($stages['build:preflight'].exit -ne 0) {
        $preflightCode = if ($LASTEXITCODE) { [int]$LASTEXITCODE } else { 125 }
        ($_ | Out-String) | Add-Content -LiteralPath $preflightLog
        $stages['build:preflight'] = @{ exit = $preflightCode; kind = 'prerequisite'; log = $preflightLog }
    }
}
# Independent diagnostics run even after preflight, configure or compilation failure; stale/missing EXEs cannot pass load checks.
$statusFile = "$wt\out\build-status-$run.json"
$stages | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 -LiteralPath $statusFile
Write-Output "checks started: $run"
& python -u -I "$wt\scripts\run-checks-profiled.py" --runner $Checks --repo $wt --out "$wt\out\checks-$run.txt" --base $loadBase --build-start $start --run $run --build-status $statusFile
$code = $LASTEXITCODE
if ($code -ne 0) { Write-Output "checks failed (exit $code), see out\checks-$run.txt" }
exit $code
