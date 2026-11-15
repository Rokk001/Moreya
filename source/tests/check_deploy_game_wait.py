"""Exercise the deploy wait without starting, closing, or deploying the real game."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
helper = root / 'scripts/win32/wait-game-exit.ps1'
deploy = (root / 'scripts/win32/orchestrator-deploy.ps1').read_text(encoding='utf-8')
assert '--game-wait-seconds $GameWaitSeconds' in deploy
assert 'odp_deployment.py' in deploy
assert 'exit $LASTEXITCODE' in deploy
assert '[int]$GameWaitSeconds = 1800' in deploy

# Execute the real wrapper with an inert helper to verify forwarding and failure propagation.
for bound, exit_code in [(0, 1), (23, 0)]:
    wrapper = str(root / 'scripts/win32/orchestrator-deploy.ps1').replace("'", "''")
    setup = r'''
function python {
    if ($args[-2] -ne '--game-wait-seconds' -or $args[-1] -ne __BOUND__) {
        throw 'Wrapper lost the configured wait bound'
    }
    if ($args[0] -ne '-I' -or $args[2] -ne 'deploy') { throw 'Wrong helper invocation' }
    $global:LASTEXITCODE = __EXIT__
}
& '__WRAPPER__' -Counter unused -DeployScript unused -GameWaitSeconds __BOUND__
'''.replace('__BOUND__', str(bound)).replace('__EXIT__', str(exit_code)).replace('__WRAPPER__', wrapper)
    result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', setup],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == exit_code, result.stdout + result.stderr

harness = r'''
$ErrorActionPreference = 'Stop'
. '__HELPER__'
# Return fixed process observations without inspecting the owner's processes.
function Get-Process {
    param($Name, $ErrorAction)
    if ($Name -ne 'opendungeons-plus') { throw 'Wrong process name' }
    $script:queries += 1
    if ($script:alwaysRunning -or $script:queries -le $script:busyQueries) {
        [pscustomobject]@{ Id = 123 }
    }
}
# Record polling without sleeping or touching any process.
function Start-Sleep {
    param($Milliseconds)
    if ($Milliseconds -lt 1 -or $Milliseconds -gt 1000) { throw 'Invalid poll interval' }
    $script:sleeps += 1
}
# Any attempt to close a process is a regression.
function Stop-Process { throw 'Must never stop a process' }
# Check the expected result and fixed poll counts for one process sequence.
function Test-WaitCase {
    param($BusyQueries, $Timeout, $ExpectedQueries, $ExpectedSleeps, $ShouldFail)
    $script:queries = 0
    $script:sleeps = 0
    $script:busyQueries = $BusyQueries
    $script:alwaysRunning = $ShouldFail
    $failed = $false
    try { Wait-GameExit -TimeoutSeconds $Timeout }
    catch {
        if ($_.Exception.Message -notlike '*deployment was not started*') { throw }
        $failed = $true
    }
    if ($failed -ne $ShouldFail) { throw 'Wrong wait result' }
    if ($script:queries -ne $ExpectedQueries) { throw 'Wrong process query count' }
    if ($script:sleeps -ne $ExpectedSleeps) { throw 'Wrong sleep count' }
}
# No game: immediate success, including a zero deadline.
Test-WaitCase 0 0 1 0 $false
# A game active at Deploy entry closes naturally: wait then proceed.
Test-WaitCase 2 30 3 2 $false
# Persistent game: fail before deployment even with a zero deadline.
Test-WaitCase 0 0 1 0 $true
# A real deadline expires even when the process never exits.
$script:alwaysRunning = $true
$timer = [Diagnostics.Stopwatch]::StartNew()
try { Wait-GameExit -TimeoutSeconds 1; throw 'Expected timeout' }
catch { if ($_.Exception.Message -notlike '*deployment was not started*') { throw } }
if ($timer.Elapsed.TotalSeconds -gt 5) { throw 'Wait exceeded its deadline' }
Write-Output 'PASS: four deploy game-wait regressions'
'''.replace('__HELPER__', str(helper).replace("'", "''"))
result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', harness],
                        capture_output=True, text=True, timeout=15)
print(result.stdout, end='')
assert result.returncode == 0, result.stderr

# Exercise the merged helper through its focused shared-lock deployment regressions.
# The receipt, guarded deployment and counter checks run alongside timeout/no-deploy cases.
result = subprocess.run([sys.executable, '-I',
                         str(root / 'scripts/check-deploy-recovery.py')],
                        capture_output=True, text=True, timeout=30)
print(result.stdout, end='')
print(result.stderr, end='')
assert result.returncode == 0, result.stdout + result.stderr
print('PASS: merged shared-lock deployment and bounded-wait regressions')
