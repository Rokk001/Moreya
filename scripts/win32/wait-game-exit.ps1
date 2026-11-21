<# Waits for the owner to close the game without terminating any process. #>
function Wait-GameExit {
    param(
        [ValidateRange(0, 86400)][int]$TimeoutSeconds = 1800
    )
    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    $announced = $false
    while (Get-Process -Name 'moreya' -ErrorAction SilentlyContinue) {
        if (-not $announced) {
            Write-Output "Waiting up to $TimeoutSeconds seconds for moreya.exe to close; no process will be stopped."
            $announced = $true
        }
        $remaining = $TimeoutSeconds - $timer.Elapsed.TotalSeconds
        if ($remaining -le 0) {
            throw "moreya.exe is still running after $TimeoutSeconds seconds; deployment was not started. Close the game and retry."
        }
        Start-Sleep -Milliseconds ([int][Math]::Min(1000, [Math]::Ceiling($remaining * 1000)))
    }
}
