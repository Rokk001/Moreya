"""Exercise the deploy wait without starting, closing, or deploying the real game."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
helper = root / 'scripts/win32/wait-game-exit.ps1'
deploy = (root / 'scripts/win32/orchestrator-deploy-selected.ps1').read_text(encoding='utf-8')
assert deploy.index('Wait-GameExit -TimeoutSeconds $GameWaitSeconds') < deploy.index('& powershell -NoProfile -File $DeployScript')
assert "$ErrorActionPreference = 'Stop'" in deploy
assert '[int]$GameWaitSeconds = 1800' in deploy

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

# Execute the actual child deployment command against a harmless deployment stub.
command_assignment = deploy[deploy.index('$waitHelper ='):deploy.index('$data = Join-Path $repo')]
with tempfile.TemporaryDirectory(prefix='deploy-wait-') as temporary:
    folder = Path(temporary)
    stub = folder / 'deploy.ps1'
    marker = folder / 'deployed.txt'
    stub.write_text("param($ExeDir, $SelectionFile)\nSet-Content -LiteralPath '"
                    + str(marker).replace("'", "''") + "' -Value 'deployed'\n", encoding='utf-8')
    for busy_queries, expected_code in [(2, 0), (100, 1)]:
        marker.unlink(missing_ok=True)
        (folder / 'scripts/win32').mkdir(parents=True, exist_ok=True)
        (folder / 'scripts/win32/wait-game-exit.ps1').write_text(helper.read_text(), encoding='utf-8')
        setup = "$ErrorActionPreference = 'Stop'\n$DeployScript = '" + str(stub).replace("'", "''") + "'\n"
        setup += "$waitScriptLiteral = '" + str(helper).replace("'", "''") + "'\n"
        setup += "$wt = '" + str(folder).replace("'", "''") + "'\n$manifest = 'fixture'\n$GameWaitSeconds = " + ('30' if expected_code == 0 else '0') + "\n"
        setup += "$script:queries = 0\nfunction Get-Process { $script:queries++; if ($script:queries -le " + str(busy_queries) + ") { 'running' } }\n"
        setup += "function Start-Sleep {}\nfunction Stop-Process { throw 'Must never stop a process' }\n"
        result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command',
                                 setup + command_assignment],
                                capture_output=True, text=True, timeout=15)
        assert result.returncode == expected_code, result.stdout + result.stderr
        assert marker.exists() == (expected_code == 0), 'Deployment must run only after the game exits'
print('PASS: two child-command deployment regressions')
