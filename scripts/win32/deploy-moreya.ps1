# Deploy a released Moreya build to the fixed folder build\windows of the main checkout (the owner always starts
# build\windows\moreya.exe there). Called by scripts/odp_deployment.py (deploy, with --integration-ref) after the build
# of the released commit was validated; it can also run on its own with the same arguments.
#
# Usage: powershell -NoProfile -File scripts\win32\deploy-moreya.ps1 -ExeDir <build\windows of the built worktree>
#            -SelectionFile <deployment selection manifest> [-IntegrationRef origin/main] [-Repo <main checkout>]
#            [-Content <content repository>] [-CheckOnly]
#   -ExeDir          Release build folder that holds moreya.exe, the DLLs, plugins.cfg and resources.cfg.
#   -SelectionFile   required deployment selection manifest (Mossgate plus changed levels) whose tip is the deployed commit.
#   -IntegrationRef  <remote>/<branch> that must contain the deployed commit; default ODP_DEPLOY_INTEGRATION_REF (set by
#                    odp_deployment.py), else origin/main.
#   -Repo            main checkout whose build\windows is the fixed folder; default the main checkout of the shared Git
#                    directory of -ExeDir (the same folder odp_deployment.py probes).
#   -Content         checkout of the private content repository; default the parent of MOREYA_CONTENT_DIR when it
#                    names a packages folder, else MOREYA_CONTENT_DIR itself, else Moreya-Content next to the main checkout.
#                    The game does not start without its content packages (it quits with exit code 7), so an empty
#                    MOREYA_CONTENT_DIR refuses the deploy before anything is changed.
#   -CheckOnly       only checks the resources.cfg of -ExeDir; exit 0 = pass, nothing is changed.
#   ODP_DEPLOY_EXPECTED_COMMIT (environment, set by odp_deployment.py): the deploy refuses a selection with another commit.
#
# What it does:
#  1. checks out the selected commit (contained in -IntegrationRef) detached in build\current-worktree (data snapshot),
#  2. installs the content, wing and room packages of the committed HEAD of the content repository (wing 1 included;
#     the public tree holds no wing) into levels\campaign of the snapshot, where the game finds them as the release
#     package does, replacing the packages of the previous deploy,
#  3. backs up the old exe/cfgs of build\windows once and records the old junction targets (rollback),
#  4. copies moreya.exe, its symbols, all DLLs, plugins.cfg and resources.cfg from -ExeDir to build\windows,
#  5. points the data junctions of build\windows to build\current-worktree.
# It never touches the working files or the index of the main checkout.
param(
    [Parameter(Mandatory = $true)][string]$ExeDir,
    [string]$SelectionFile,
    [string]$IntegrationRef = '',
    [string]$Repo = '',
    [string]$Content = '',
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$exeName = 'moreya.exe'
$processName = 'moreya'
$pdbName = 'moreya.pdb'
# The agreed basis level: Mossgate in the wing 1 package (a content package now, installed below levels\campaign in
# step 2; the selection keeps its former public path as its name), or at its former path in older commits
$smokeLevels = 'levels/campaign/wing1/Mossgate.level', 'levels/campaign/Mossgate.level'
if (-not $CheckOnly) {
    if (-not $SelectionFile -or -not (Test-Path -LiteralPath $SelectionFile -PathType Leaf)) {
        throw 'Moreya deployment requires a verified Mossgate-plus-changed-levels selection manifest.'
    }
    $selection = Get-Content -Raw -LiteralPath $SelectionFile | ConvertFrom-Json
    $hasSmoke = $false
    if ($selection.levels) { foreach ($smoke in $smokeLevels) { if ($selection.levels.$smoke) { $hasSmoke = $true } } }
    if ($selection.schema -ne 1 -or $selection.tip -notmatch '^[0-9a-f]{40}$' -or
        $selection.mode -notin @('selected', 'full') -or -not $selection.levels -or
        ($selection.mode -eq 'selected' -and ($selection.base -notmatch '^[0-9a-f]{40}$' -or -not $hasSmoke))) {
        throw 'Invalid deployment selection; no files were deployed.'
    }
}
# Services can inherit an incomplete module search path; load the module that supplies Get-FileHash explicitly.
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop

# git writes progress and notices to stderr; under 'Stop' PowerShell 5.1 turns that into an error. Run git with stderr
# as normal output and judge only the exit code.
function Invoke-Git {
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $out = & git @args 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE
    $ErrorActionPreference = $old
    if ($code -ne 0) { throw "git $($args -join ' ') failed with exit code $code`n$out" }
    $out
}

# Every absolute FileSystem= folder of the resources.cfg in -ExeDir must exist and must not lie inside another user's
# profile folder (C:\Users\Public is not a profile). Relative FileSystem= lines are not checked here.
function Test-DeployResourceFolders {
    param([Parameter(Mandatory = $true)][string]$Dir)
    $cfg = Join-Path $Dir 'resources.cfg'
    if (-not (Test-Path -LiteralPath $cfg -PathType Leaf)) { throw "no resources.cfg in $Dir (a release output without it is incomplete); nothing in build\windows was changed." }
    $ownProfile = [System.IO.Path]::GetFullPath($env:USERPROFILE).TrimEnd('\')
    $profilesRoot = Split-Path $ownProfile -Parent
    $otherProfiles = @(Get-ChildItem -LiteralPath $profilesRoot -Directory -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne 'Public' } |
        ForEach-Object { [System.IO.Path]::GetFullPath($_.FullName).TrimEnd('\') } |
        Where-Object { -not $_.Equals($ownProfile, [StringComparison]::OrdinalIgnoreCase) })
    $bad = @()
    foreach ($line in Get-Content -LiteralPath $cfg) {
        if ($line -notmatch '^\s*FileSystem\s*=\s*(.+?)\s*$') { continue }
        $raw = $matches[1]
        if ($raw -notmatch '^([A-Za-z]:[\/]|[\/]{2})') { continue }
        $full = [System.IO.Path]::GetFullPath($raw.Replace('/', '\')).TrimEnd('\')
        if (-not (Test-Path -LiteralPath $full -PathType Container)) { $bad += "$raw (missing)"; continue }
        foreach ($p in $otherProfiles) {
            if ($full.Equals($p, [StringComparison]::OrdinalIgnoreCase) -or $full.StartsWith($p + '\', [StringComparison]::OrdinalIgnoreCase)) {
                $bad += "$raw (inside another user's profile folder $p)"
                break
            }
        }
    }
    if ($bad.Count -gt 0) {
        throw ("resources.cfg in $Dir names $($bad.Count) folder(s) that cannot be used on this machine; nothing in build\windows was changed:`n  " + ($bad -join "`n  "))
    }
    Write-Host "resources.cfg check passed: $cfg"
}

# The content repository to deploy; an empty MOREYA_CONTENT_DIR is refused (the game does not start without content).
function Get-ContentRepository {
    param([string]$Explicit, [Parameter(Mandatory = $true)][string]$MainCheckout)
    if ($Explicit) { return (Resolve-Path -LiteralPath $Explicit).Path }
    $variable = [Environment]::GetEnvironmentVariable('MOREYA_CONTENT_DIR')
    if ($null -ne $variable) {
        if (-not $variable.Trim()) { throw 'MOREYA_CONTENT_DIR is empty: the game needs its content packages (it quits with exit code 7 without them); pass -Content or name the content packages. Nothing was changed.' }
        $folder = (Resolve-Path -LiteralPath $variable.Trim()).Path
        if ((Split-Path -Leaf $folder) -eq 'packages') { return (Split-Path -Parent $folder) }
        return $folder
    }
    $candidate = Join-Path (Split-Path -Parent $MainCheckout) 'Moreya-Content'
    if (-not (Test-Path -LiteralPath (Join-Path $candidate 'packages') -PathType Container)) {
        throw "Content repository not found at $candidate; pass -Content or set MOREYA_CONTENT_DIR. Nothing was changed."
    }
    return $candidate
}

if (-not (Test-Path -LiteralPath (Join-Path $ExeDir $exeName))) { throw "no $exeName in $ExeDir" }
$ExeDir = (Resolve-Path -LiteralPath $ExeDir).Path
if (-not $Repo) {
    $common = (Invoke-Git -C $ExeDir rev-parse --path-format=absolute --git-common-dir | Select-Object -Last 1).Trim()
    $Repo = Split-Path -Parent $common
}
$Repo = (Resolve-Path -LiteralPath $Repo).Path
if (-not $IntegrationRef) { $IntegrationRef = if ($env:ODP_DEPLOY_INTEGRATION_REF) { $env:ODP_DEPLOY_INTEGRATION_REF } else { 'origin/main' } }
if ($IntegrationRef -notmatch '^[\w.-]+/[\w./-]+$') { throw "Integration ref must be <remote>/<branch>: $IntegrationRef" }
$remote, $branch = $IntegrationRef.Split('/', 2)
$target = Join-Path $Repo 'build\windows'
$current = Join-Path $Repo 'build\current-worktree'
$backup = Join-Path $target 'deploy-backup'
$contentRecord = Join-Path $target 'deployed-content-packages.txt'
Write-Host "Moreya checkout used: $Repo; deploy folder: $target; integration ref: $IntegrationRef"
Test-DeployResourceFolders -Dir $ExeDir
if ($CheckOnly) { Write-Host 'CheckOnly: only the check ran; nothing was changed.'; exit 0 }
$contentRepo = Get-ContentRepository -Explicit $Content -MainCheckout $Repo
New-Item -ItemType Directory -Force $target | Out-Null

# Direct deployments use the same byte lock as odp_deployment.py and the load runners; the wrapper retains ownership
# through this child, its probes and the counter publication.
$lockStream = $null
$parentPid = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID" -ErrorAction Stop).ParentProcessId
$wrapperOwnsLock = $env:ODP_DEPLOY_EXPECTED_COMMIT -and $env:ODP_DEPLOY_LOCK_OWNER -eq [string]$parentPid
if (-not $wrapperOwnsLock) {
    $lockStream = [System.IO.File]::Open((Join-Path $target '.odp-executable.lock'), 'OpenOrCreate', 'ReadWrite', 'ReadWrite')
    while ($true) {
        try { $lockStream.Lock(0, 1); break }
        catch [System.IO.IOException] { Start-Sleep -Milliseconds 200 }
    }
}
$contentStage = Join-Path $target 'deploy-content-new'
try {
$dataDirs = 'config', 'gui', 'levels', 'licenses', 'materials', 'models', 'music', 'particles', 'python', 'scripts', 'shaders', 'sounds'

if (Get-Process -Name $processName -ErrorAction SilentlyContinue) { throw "$exeName is running; close it first." }

# 0. exe and data are switched together (no mixed state): the exe is first copied to a temp name in the target folder,
#    and a locked exe aborts the deploy before anything (data snapshot, DLLs, junctions) is changed.
$exeTarget = Join-Path $target $exeName
$exeTemp = Join-Path $target ($exeName + '.new')
if (Test-Path $exeTarget) {
    try { $fs = [System.IO.File]::Open($exeTarget, 'Open', 'ReadWrite', 'None'); $fs.Close() }
    catch { throw "$exeName in build\windows is locked (a game is running); nothing was changed. Close the game and retry." }
}
# Content packages of the committed HEAD of the content repository, staged before anything is switched
$contentNames = @()
$contentCommit = 'none'
if (Test-Path -LiteralPath $contentStage) { Remove-Item -LiteralPath $contentStage -Recurse -Force }
if ($contentRepo) {
    $contentCommit = (Invoke-Git -C $contentRepo rev-parse --verify 'HEAD^{commit}' | Select-Object -Last 1).Trim()
    New-Item -ItemType Directory -Force $contentStage | Out-Null
    $contentTar = Join-Path $contentStage 'content.tar'
    Invoke-Git -C $contentRepo archive --format=tar -o $contentTar HEAD packages | Out-Null
    & tar -xf $contentTar -C $contentStage
    if ($LASTEXITCODE -ne 0) { throw 'tar extract of the content packages failed; nothing was changed.' }
    Remove-Item -LiteralPath $contentTar
    $contentNames = @(Get-ChildItem -LiteralPath (Join-Path $contentStage 'packages') -Directory |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'Package.cfg') -PathType Leaf } | ForEach-Object { $_.Name })
    if ($contentNames.Count -eq 0) { throw "No wing package in $contentRepo\packages at $contentCommit; nothing was changed." }
}
Copy-Item (Join-Path $ExeDir $exeName) $exeTemp -Force

# 1. data snapshot of the pushed commit frozen by the deployment selector, never a newly advanced remote ref.
#    The content packages of the previous deploy are removed first so the checkout never meets untracked files.
$campaign = Join-Path $current 'levels\campaign'
if (Test-Path -LiteralPath $contentRecord) {
    foreach ($line in Get-Content -LiteralPath $contentRecord) {
        if ($line -notmatch '^package (\S+)$') { continue }
        $old = Join-Path $campaign $Matches[1]
        if (Test-Path -LiteralPath $old) { Remove-Item -LiteralPath $old -Recurse -Force }
    }
}
Invoke-Git -C $Repo fetch $remote $branch | Out-Null
$sha = (Invoke-Git -C $Repo rev-parse --verify ($selection.tip + '^{commit}') | Select-Object -Last 1).Trim()
Invoke-Git -C $Repo merge-base --is-ancestor $sha $IntegrationRef | Out-Null
# Reject a selection whose commit differs from the validated build before changing the data snapshot or deployed files.
if ($env:ODP_DEPLOY_EXPECTED_COMMIT -and $sha -ne $env:ODP_DEPLOY_EXPECTED_COMMIT) {
    throw 'Integration target changed after Build validation; normal integration revalidation required.'
}
if (-not (Test-Path $current)) { Invoke-Git -C $Repo worktree add --detach $current $sha | Out-Null }
else { Invoke-Git -C $current checkout --detach $sha | Out-Null }
Write-Host "data snapshot: $sha"

# 2. content, wing and room packages below levels\campaign; a package folder that the snapshot tracks is never replaced
foreach ($name in $contentNames) {
    if (Invoke-Git -C $current ls-files -- "levels/campaign/$name") { throw "Content package $name collides with a tracked folder of $sha." }
    $destination = Join-Path $campaign $name
    if (Test-Path -LiteralPath $destination) { throw "Untracked folder $destination is in the way of content package $name." }
    Copy-Item -LiteralPath (Join-Path $contentStage "packages\$name") -Destination $destination -Recurse
}
$recordLines = @("content $contentCommit") + @($contentNames | ForEach-Object { "package $_" })
Set-Content -Encoding ascii -LiteralPath $contentRecord -Value $recordLines
Write-Host "content packages: $($contentNames.Count) from $contentRepo at $contentCommit"

# 3. backup and record (once, before the first deploy into this folder)
New-Item -ItemType Directory -Force $backup | Out-Null
$record = Join-Path $backup 'junction-targets-before.txt'
if (-not (Test-Path $record)) {
    Get-ChildItem $target -Force | Where-Object { $_.LinkType } | ForEach-Object { "$($_.Name) -> $($_.Target)" } | Set-Content $record
    foreach ($f in $exeName, 'plugins.cfg', 'resources.cfg') {
        if (Test-Path -LiteralPath (Join-Path $target $f)) { Copy-Item (Join-Path $target $f) (Join-Path $backup $f) -Force }
    }
}

# 4. copy DLLs and cfgs; the exe is swapped in with one rename right before the data junctions are switched (step 5)
Get-ChildItem $ExeDir -File | Where-Object { $_.Extension -in '.dll', '._pth' -or $_.Name -like 'python*._pth' } | ForEach-Object { Copy-Item $_.FullName $target -Force }
foreach ($f in 'plugins.cfg', 'resources.cfg') { if (Test-Path (Join-Path $ExeDir $f)) { Copy-Item (Join-Path $ExeDir $f) $target -Force } }
# ogre-includes is a relative resource folder of resources.cfg
$includes = Join-Path $ExeDir 'ogre-includes'
if (Test-Path -LiteralPath $includes -PathType Container) {
    & robocopy $includes (Join-Path $target 'ogre-includes') /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy ogre-includes failed ($LASTEXITCODE)" }
}

# Keep symbols paired with the deployed executable; remove symbols from an older build.
$pdbSource = Join-Path $ExeDir $pdbName
$pdbTarget = Join-Path $target $pdbName
if (Test-Path -LiteralPath $pdbSource -PathType Leaf) {
    Copy-Item -LiteralPath $pdbSource -Destination $pdbTarget -Force
} elseif (Test-Path -LiteralPath $pdbTarget) {
    Remove-Item -LiteralPath $pdbTarget -Force
}

# 5. swap the exe (rename of the prepared temp file) and point the data junctions right after it
Move-Item $exeTemp $exeTarget -Force
foreach ($d in $dataDirs) {
    $link = Join-Path $target $d
    $source = Join-Path $current $d
    if (Test-Path $link) {
        if (-not (Get-Item -LiteralPath $link -Force).LinkType) { throw "$link is a real folder, not a data junction; it was left unchanged." }
        cmd /c rmdir "$link" | Out-Null   # removes the junction only, never the target
    }
    if (Test-Path -LiteralPath $source -PathType Container) { cmd /c mklink /J "$link" $source | Out-Null }
}
$hash = (Get-FileHash $exeTarget).Hash.Substring(0, 12)
Write-Host "deployed $exeName $hash from $ExeDir; data from $current at $sha; start $exeTarget"

} finally {
    if (Test-Path -LiteralPath $contentStage) { Remove-Item -LiteralPath $contentStage -Recurse -Force }
    if ($lockStream) { $lockStream.Unlock(0, 1); $lockStream.Dispose() }
}
