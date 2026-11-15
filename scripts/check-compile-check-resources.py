"""Exercise compile-check resource admission without starting builds or compilers."""
import pathlib
import subprocess
import tempfile
import unittest


SCRIPT = pathlib.Path(__file__).resolve().parent / 'win32/compile-check-changed.ps1'


class ResourceAdmission(unittest.TestCase):
    """Keep build exclusion, the 2048 MB floor and a shared bounded wait."""

    def run_gate(self, builds, memory, minutes=2):
        """Run the production admission block with a deterministic clock and resources."""
        source = SCRIPT.read_text(encoding='utf-8-sig')
        gate = source[source.index('# Wait while a full build'):source.index('$files = @')]
        fixture = r'''
$ErrorActionPreference = 'Stop'
$script:tick = 0
$builds = @(__BUILDS__)
$memory = @(__MEMORY__)
$MaxWaitMinutes = __MINUTES__
function Get-Date { return ([datetime]'2026-01-01').AddSeconds(30 * $script:tick) }
function Start-Sleep {
    param($Seconds)
    if ($Seconds -ne 30) { throw 'unexpected polling interval' }
    $script:tick++
    if ($script:tick -gt 10) { throw 'unbounded resource wait' }
}
function Get-FullBuildCount { return $builds[[math]::Min($script:tick, $builds.Count - 1)] }
function Get-CimInstance {
    param($ClassName)
    if ($ClassName -ne 'Win32_OperatingSystem') { throw 'unexpected resource query' }
    return [pscustomobject]@{FreePhysicalMemory = 1024 * $memory[[math]::Min($script:tick, $memory.Count - 1)]}
}
function Write-CheckLog { param($text) Write-Output $text }
'''
        fixture = fixture.replace('__BUILDS__', ','.join(map(str, builds)))
        fixture = fixture.replace('__MEMORY__', ','.join(map(str, memory)))
        fixture = fixture.replace('__MINUTES__', str(minutes))
        with tempfile.TemporaryDirectory() as folder:
            probe = pathlib.Path(folder) / 'admission.ps1'
            probe.write_text(fixture + gate + '\nWrite-Output "ADMITTED tick=$script:tick"\n')
            return subprocess.run(
                ['powershell', '-NoProfile', '-File', str(probe)],
                capture_output=True, text=True, timeout=15)

    def test_build_then_low_ram_then_recovery(self):
        """Reproduce the failed run's 1606 MB reading after a full build ends."""
        result = self.run_gate([1, 0, 0], [4096, 1606, 2048])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('waiting: a full build is running', result.stdout)
        self.assertIn('waiting: RAM too low: 1606 MB', result.stdout)
        self.assertIn('ADMITTED tick=2', result.stdout)

    def test_memory_floor(self):
        """A check with no full build still waits below the unchanged RAM floor."""
        result = self.run_gate([0], [2047, 2048])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('ADMITTED tick=1', result.stdout)

    def test_ready_immediately(self):
        """Exactly 2048 MB admits compilation immediately when no build runs."""
        result = self.run_gate([0], [2048])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('ADMITTED tick=0', result.stdout)

    def test_build_restarts_during_memory_wait(self):
        """Recheck full builds on every poll, including after a low RAM reading."""
        result = self.run_gate([0, 1, 0], [1606, 4096, 4096])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('waiting: a full build is running', result.stdout)
        self.assertIn('ADMITTED tick=2', result.stdout)

    def test_low_memory_timeout(self):
        """Persistent low RAM fails closed with the existing resource exit code."""
        result = self.run_gate([0], [1606], minutes=1)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn('WAIT_TIMEOUT: RAM too low: 1606 MB', result.stdout)
        self.assertNotIn('ADMITTED', result.stdout)

    def test_full_build_timeout(self):
        """Persistent full builds retain their distinct timeout exit code."""
        result = self.run_gate([1], [4096], minutes=1)
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertIn('WAIT_TIMEOUT: a full build still runs', result.stdout)
        self.assertNotIn('ADMITTED', result.stdout)

    def test_build_and_ram_share_deadline(self):
        """Changing wait reasons must not restart the configured timeout."""
        result = self.run_gate([1, 1, 0], [4096, 4096, 1606], minutes=1)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn('WAIT_TIMEOUT: RAM too low: 1606 MB', result.stdout)
        self.assertNotIn('waiting: RAM too low', result.stdout)
        self.assertNotIn('ADMITTED', result.stdout)


if __name__ == '__main__':
    unittest.main()
