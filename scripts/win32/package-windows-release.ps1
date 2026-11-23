# Assembles the self-contained Windows x64 release of Moreya from a Release build tree and packs it as
# Moreya-<version>-windows-x64.zip (one top folder of the same name).
#
# Usage: powershell -NoProfile -File scripts\win32\package-windows-release.ps1 [-Build <build dir>] [-OutDir <folder>]
#            [-Content <content repository>]
#   -Build   Release build tree that holds moreya.exe, plugins.cfg, resources.cfg and ogre-includes
#            (default build\windows of this worktree)
#   -OutDir  folder for the game folder and the zip archive (default out\package of this worktree);
#            the game folder and the zip must not exist yet.
#   -Content checkout of the private campaign content repository (the Steam build); the wing packages and room
#            packages of its packages folder at its HEAD are added to levels\campaign next to the wing 1 package.
#            Without it the package holds the public game: wing 1 playable, wings 2 to 6 locked, the packaged rooms
#            unavailable.
#
# Follows the WIN32 install rules of CMakeLists.txt (exe, OGRE/CEGUI/SFML/OIS libraries and the MSVC runtime,
# plugins.cfg, resources.cfg, the game data folders and the documents), the runtime list of
# prepare-windows-runtime.ps1 and the OGRE media handling of scripts/unix/package-linux-release.sh.
# Game data and documents come from the committed content of HEAD (git archive), never from local changes.
# The version is OD_MAJOR_VERSION.OD_MINOR_VERSION.OD_PATCH_LEVEL of CMakeLists.txt and OD_BUILD_NUMBER of the build tree.
# Machine locations come from windows-paths.ps1 (BUILD_DEPS_ROOT, BUILD_PYTHON_ROOT, BUILD_VS_PATH).
param(
    [string]$Build = '',
    [string]$OutDir = '',
    [string]$Content = ''
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'windows-paths.ps1')
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $Build) { $Build = Join-Path $repo 'build\windows' }
if (-not $OutDir) { $OutDir = Join-Path $repo 'out\package' }
$Build = (Resolve-Path -LiteralPath $Build).Path
$deps = Join-Path $taskDependencyRoot 'install'
$python = $taskPythonRoot

# Version: major, minor and patch from CMakeLists.txt, the build number from the configured build tree
$cmakeLists = Get-Content -Raw -LiteralPath (Join-Path $repo 'CMakeLists.txt')
$parts = foreach ($name in 'OD_MAJOR_VERSION', 'OD_MINOR_VERSION', 'OD_PATCH_LEVEL') {
    if ($cmakeLists -notmatch "set\($name\s+([0-9]+)\)") { throw "$name not found in CMakeLists.txt" }
    $Matches[1]
}
$cache = Get-Content -Raw -LiteralPath (Join-Path $Build 'CMakeCache.txt')
if ($cache -notmatch '(?m)^OD_BUILD_NUMBER:STRING=([0-9]+)') { throw 'OD_BUILD_NUMBER not found in the build tree' }
$version = ($parts + $Matches[1]) -join '.'
$name = "Moreya-$version-windows-x64"
$Out = Join-Path $OutDir $name
$zip = Join-Path $OutDir "$name.zip"
if ((Test-Path -LiteralPath $Out) -or (Test-Path -LiteralPath $zip)) { throw "output exists already: $Out or $zip" }
New-Item -ItemType Directory -Force $Out | Out-Null

# Game executable (the CMake target opendungeons-plus writes moreya.exe)
$exe = Join-Path $Build 'moreya.exe'
if (-not (Test-Path -LiteralPath $exe)) { $exe = Join-Path $Build 'Release\moreya.exe' }
if (-not (Test-Path -LiteralPath $exe)) { throw "moreya.exe not found in $Build" }
Copy-Item -LiteralPath $exe -Destination $Out

# Game data and documents: tracked content of HEAD only; scripts/ holds developer tools and is not shipped
$dataDirs = 'config', 'gui', 'levels', 'licenses', 'materials', 'models', 'music', 'particles', 'python', 'shaders', 'sounds'
$docs = 'AUTHORS', 'CREDITS', 'LICENSE.md', 'README.md', 'RELEASE-NOTES.md'
$tar = Join-Path $OutDir "$name-data.tar"
& git -C $repo archive --format=tar -o $tar HEAD @dataDirs @docs
if ($LASTEXITCODE -ne 0) { throw 'git archive failed' }
& tar -xf $tar -C $Out
if ($LASTEXITCODE -ne 0) { throw 'tar extract failed' }
Remove-Item -LiteralPath $tar
# Content packages of the private content repository (committed content of its HEAD only): wings and rooms
if ($Content) {
    $contentTar = Join-Path $OutDir "$name-content.tar"
    & git -C (Resolve-Path -LiteralPath $Content).Path archive --format=tar -o $contentTar HEAD packages
    if ($LASTEXITCODE -ne 0) { throw 'git archive of the content packages failed' }
    $contentDir = Join-Path $OutDir "$name-content"
    New-Item -ItemType Directory -Force $contentDir | Out-Null
    & tar -xf $contentTar -C $contentDir
    if ($LASTEXITCODE -ne 0) { throw 'tar extract of the content packages failed' }
    Get-ChildItem -LiteralPath (Join-Path $contentDir 'packages') -Directory |
        ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $Out 'levels\campaign') -Recurse }
    Remove-Item -LiteralPath $contentTar
    Remove-Item -LiteralPath $contentDir -Recurse
}

# Libraries: the external libraries of the install rules and the runtime list of prepare-windows-runtime.ps1
$dlls = 'OgreMain.dll', 'OgreOverlay.dll', 'OgreRTShaderSystem.dll', 'OgreBites.dll',
    'Plugin_OctreeSceneManager.dll', 'Plugin_ParticleFX.dll', 'RenderSystem_GL3Plus.dll', 'Codec_STBI.dll',
    'CEGUIBase-0.dll', 'CEGUICoreWindowRendererSet.dll', 'CEGUIExpatParser.dll', 'CEGUIOgreRenderer-0.dll',
    'sfml-audio-3.dll', 'sfml-network-3.dll', 'sfml-system-3.dll', 'OIS.dll', 'freetype.dll', 'libexpat.dll'
foreach ($dll in $dlls) { Copy-Item -LiteralPath (Join-Path "$deps\bin" $dll) -Destination $Out }
# MSVC runtime (CMAKE_INSTALL_SYSTEM_RUNTIME_LIBS): the newest redistributable folder of the build tools
$crt = Get-ChildItem -LiteralPath (Join-Path $taskVsPath 'VC\Redist\MSVC') -Directory -ErrorAction SilentlyContinue |
    Sort-Object Name -Descending | ForEach-Object { Join-Path $_.FullName 'x64' } | Where-Object { Test-Path -LiteralPath $_ } |
    ForEach-Object { Get-ChildItem -LiteralPath $_ -Directory -Filter 'Microsoft.VC*.CRT' } | Select-Object -First 1
if (-not $crt) { throw "MSVC runtime not found below $taskVsPath\VC\Redist\MSVC" }
Get-ChildItem -LiteralPath $crt.FullName -Filter '*.dll' | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $Out }

# Embedded Python runtime and standard library, resolved relative to the Python DLL
Copy-Item -LiteralPath "$python\python314.dll", "$python\python3.dll" -Destination $Out
& robocopy "$python\Lib" "$Out\Lib" /E /NFL /NDL /NJH /NJS /NP /XD __pycache__ test idlelib tkinter turtledemo ensurepip site-packages | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy Lib failed ($LASTEXITCODE)" }
& robocopy "$python\DLLs" "$Out\DLLs" /E /NFL /NDL /NJH /NJS /NP /XF _tkinter.pyd tcl*.dll tk*.dll | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy DLLs failed ($LASTEXITCODE)" }
[System.IO.File]::WriteAllLines((Join-Path $Out 'python314._pth'), [string[]]@('.', 'Lib', 'DLLs', 'import site'))

# OGRE media used by resources.cfg and the shared shader includes
New-Item -ItemType Directory -Force "$Out\ogre-media" | Out-Null
foreach ($media in 'RTShaderLib', 'Main') {
    & robocopy "$deps\Media\$media" "$Out\ogre-media\$media" /E /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy $media failed ($LASTEXITCODE)" }
}
& robocopy "$Build\ogre-includes" "$Out\ogre-includes" /E /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy ogre-includes failed ($LASTEXITCODE)" }

# plugins.cfg: plugins beside the exe (an empty PluginFolder is the exe folder)
Copy-Item -LiteralPath (Join-Path $Build 'plugins.cfg') -Destination $Out
# resources.cfg: absolute OGRE media paths become the bundled relative folders
$lines = foreach ($line in Get-Content -LiteralPath (Join-Path $Build 'resources.cfg')) {
    if ($line -match '^FileSystem=.*/Media/RTShaderLib/\.\./Main$') { 'FileSystem=ogre-media/Main' }
    elseif ($line -match '^FileSystem=.*/Media/(.+)$') { 'FileSystem=ogre-media/' + $Matches[1] }
    else { $line }
}
[System.IO.File]::WriteAllLines((Join-Path $Out 'resources.cfg'), [string[]]$lines)
foreach ($line in $lines) {
    if ($line -match '^FileSystem=(.+)$') {
        $path = $Matches[1]
        if ([System.IO.Path]::IsPathRooted($path)) { throw "absolute path left in resources.cfg: $path" }
        if (-not (Test-Path -LiteralPath (Join-Path $Out $path) -PathType Container)) { throw "resource folder missing: $path" }
    }
}

# Archive with the game folder as its single top folder
Compress-Archive -LiteralPath $Out -DestinationPath $zip
Write-Output "packaged $Out"
Write-Output "archive $zip"
