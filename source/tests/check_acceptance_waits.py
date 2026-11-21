"""Exercise readiness and screenshot waits in PowerShell without sending input to a game."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = r'''
param([string]$Helper, [string]$Work)
$ErrorActionPreference = 'Stop'
. $Helper
Add-Type -AssemblyName System.Drawing
# Assert a regression condition with a useful failure message.
function Assert($Value, [string]$Message) { if(-not $Value) { throw $Message } }
# Verify that missing readiness is reported as an error, never success.
function Assert-Throws([scriptblock]$Code, [string]$Pattern) {
    try { & $Code | Out-Null } catch { Assert ($_.Exception.Message -match $Pattern) $_; return }
    throw "Expected failure: $Pattern"
}
$script:sleeps = 0
# Record polling and advance quickly; production retains its real bounded polling interval.
function Start-Sleep([int]$Milliseconds) {
    $script:sleeps++
    Microsoft.PowerShell.Utility\Start-Sleep -Milliseconds 1
}
Assert ((Wait-GameCondition { 'ready' } 1 'ready') -eq 'ready') 'immediate success lost'
Assert ($script:sleeps -eq 0) 'unnecessary sleep on ready state'
$script:queries = 0
Assert ((Wait-GameCondition { $script:queries++; if($script:queries -eq 3) { 'ready' } } 1 'delayed') -eq 'ready') 'delayed readiness lost'
Assert ($script:sleeps -eq 2) 'polling must stop at readiness'
Assert-Throws { Wait-GameCondition { $false } .02 'never ready' } 'Timed out'
Assert-Throws { Wait-GameCondition { throw 'process died' } 1 'dead' } 'process died'
$process = [pscustomobject]@{HasExited=$false; MainWindowHandle=[IntPtr]1; Responding=$true; ExitCode=7}
$process | Add-Member ScriptMethod Refresh { }
Assert (-not (Test-GameReady $process $Work $false)) 'window alone is not startup readiness'
Set-Content (Join-Path $Work 'moreya.log') 'startup menu ready'
Assert (Test-GameReady $process $Work $false) 'ready menu not detected'
Assert (-not (Test-GameReady $process $Work $true)) 'menu marker must not accept an unloaded level'
Set-Content (Join-Path $Work 'acceptance-stdout.txt') 'GOALS registered=0'
Assert (-not (Test-GameReady $process $Work $true)) 'zero goals accepted'
Set-Content (Join-Path $Work 'acceptance-stdout.txt') 'GOALS registered=2'
Assert (Test-GameReady $process $Work $true) 'ready level not detected'
$process.Responding=$false
Assert (-not (Test-GameReady $process $Work $true)) 'hung window accepted'
$process.HasExited=$true
Assert-Throws { Test-GameReady $process $Work $true } 'exited early.*7'
$shot = Join-Path $Work 'ODscreenshot_test.png'
$since = [datetime]::UtcNow.AddMinutes(-1)
Assert ($null -eq (Get-NewGameScreenshot $Work $since @{})) 'missing screenshot accepted'
[IO.File]::WriteAllBytes($shot, [byte[]](137,80,78,71))
Assert ($null -eq (Get-NewGameScreenshot $Work $since @{})) 'partial screenshot accepted'
$bitmap = New-Object Drawing.Bitmap 2,2
try { $bitmap.Save($shot, [Drawing.Imaging.ImageFormat]::Png) } finally { $bitmap.Dispose() }
$complete = [IO.File]::ReadAllBytes($shot)
[IO.File]::WriteAllBytes($shot, $complete[0..($complete.Length-13)])
Assert ($null -eq (Get-NewGameScreenshot $Work $since @{})) 'PNG without final chunk accepted'
[IO.File]::WriteAllBytes($shot, $complete)
$existing = @{}; $existing[$shot] = (Get-Item $shot).LastWriteTimeUtc.Ticks
Assert ($null -eq (Get-NewGameScreenshot $Work $since $existing)) 'old screenshot accepted'
$lock = [IO.File]::Open($shot, 'Open', 'ReadWrite', 'None')
try { Assert ($null -eq (Get-NewGameScreenshot $Work $since @{})) 'open screenshot accepted' } finally { $lock.Dispose() }
Assert ((Get-NewGameScreenshot $Work $since @{}).FullName -eq $shot) 'complete screenshot rejected'
Write-Output 'PASS: immediate/delayed readiness, timeout, process failure, menu/level markers, hung window, missing/partial/old/locked/complete screenshots'
'''
with tempfile.TemporaryDirectory(prefix='odp-wait-tests-') as temporary:
    work = Path(temporary)
    script = work / 'test.ps1'
    script.write_text(SCRIPT, encoding='utf-8')
    subprocess.run(['powershell', '-NoProfile', '-File', str(script),
                    '-Helper', str(ROOT / 'scripts/acceptance/wait-game-state.ps1'),
                    '-Work', str(work)], check=True, timeout=30)
source = (ROOT / 'scripts/acceptance/ingame-input.ps1').read_text()
assert 'Start-Sleep $Wait' not in source and 'Start-Sleep 4' not in source
assert 'Test-GameReady $proc $appData ([bool]$Level)' in source
assert 'Get-NewGameScreenshot $state.AppData $before $existing' in source
assert source.index('Get-NewGameScreenshot $state.AppData') < source.index('Copy-Item $shot.FullName')
