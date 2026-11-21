# Wait for observable readiness, failing on timeout instead of assuming a fixed pause was sufficient.
function Wait-GameCondition([scriptblock]$Condition, [double]$TimeoutSeconds, [string]$Description)
{
    $clock = [System.Diagnostics.Stopwatch]::StartNew()
    while($true)
    {
        $result = & $Condition
        if($result) { return $result }
        $remaining = $TimeoutSeconds * 1000 - $clock.Elapsed.TotalMilliseconds
        if($remaining -le 0) { throw "Timed out waiting for $Description." }
        Start-Sleep -Milliseconds ([int][Math]::Min(100, [Math]::Ceiling($remaining)))
    }
}

# Refuse to treat an exited process or a loading window as a ready game.
function Test-GameReady($Process, [string]$AppData, [bool]$LevelRequested)
{
    $Process.Refresh()
    if($Process.HasExited) { throw "The game exited early with code $($Process.ExitCode)." }
    if($Process.MainWindowHandle -eq [IntPtr]::Zero -or -not $Process.Responding) { return $false }
    $name = if($LevelRequested) { 'acceptance-stdout.txt' } else { 'moreya.log' }
    $marker = if($LevelRequested) { '(?m)^GOALS registered=[1-9][0-9]*' } else { 'startup menu ready' }
    $path = Join-Path $AppData $name
    if(-not (Test-Path -LiteralPath $path)) { return $false }
    try { return [bool]((Get-Content -Raw -LiteralPath $path -ErrorAction Stop) -match $marker) }
    catch [System.IO.IOException] { return $false }
}

# Accept only a new, closed and decodable PNG; old or partially written screenshots are not results.
function Get-NewGameScreenshot([string]$AppData, [datetime]$Since, [hashtable]$Existing)
{
    $shots = Get-ChildItem -LiteralPath $AppData -Recurse -Filter 'ODscreenshot_*.png' -ErrorAction Stop |
        Where-Object { $_.LastWriteTimeUtc -ge $Since.ToUniversalTime() -and
            (-not $Existing.ContainsKey($_.FullName) -or $_.LastWriteTimeUtc.Ticks -gt $Existing[$_.FullName]) } |
        Sort-Object LastWriteTimeUtc -Descending
    foreach($shot in $shots)
    {
        $stream = $null
        $picture = $null
        try
        {
            $stream = [System.IO.File]::Open($shot.FullName, 'Open', 'Read', 'None')
            if($stream.Length -lt 12) { continue }
            $stream.Seek(-12, [System.IO.SeekOrigin]::End) | Out-Null
            $end = New-Object byte[] 12
            if($stream.Read($end, 0, 12) -ne 12 -or
                [BitConverter]::ToString($end) -ne '00-00-00-00-49-45-4E-44-AE-42-60-82') { continue }
            $stream.Position = 0
            $picture = [System.Drawing.Image]::FromStream($stream, $false, $true)
            if($picture.Width -gt 0 -and $picture.Height -gt 0) { return $shot }
        }
        catch [System.IO.IOException] { continue }
        catch [System.ArgumentException] { continue }
        catch [System.OutOfMemoryException] { continue } # GDI+ also uses this error for incomplete images.
        finally
        {
            if($picture) { $picture.Dispose() }
            if($stream) { $stream.Dispose() }
        }
    }
    return $null
}
