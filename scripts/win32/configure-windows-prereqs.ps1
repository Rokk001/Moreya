# BuildNumber is the fourth version digit; only integrator release builds pass N > 0, all others keep 0.
param([int]$BuildNumber = 0)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'windows-paths.ps1')
. (Join-Path $PSScriptRoot 'ogre-prereq-provenance.ps1')
Assert-OgrePrereqProvenance -DependencyRoot $taskDependencyRoot
. (Join-Path $PSScriptRoot 'Enter-OpenDungeonsPlus.ps1')
$taskRepo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
# Keep configuration logs local to the worktree so concurrent integrations do not share a log file.
$taskLogDirectory = Join-Path $taskRepo 'out'
New-Item -ItemType Directory -Force -Path $taskLogDirectory | Out-Null
$taskConfigureLog = Join-Path $taskLogDirectory ("opendungeons-configure-{0}.log" -f [guid]::NewGuid().ToString('N'))
# Recreate CMake's cache so a build directory copied from another checkout can be configured here.
$taskOptions = @('--fresh', '-S', $taskRepo, '-B', "$taskRepo\build\windows",
    '-G', 'Visual Studio 18 2026', '-A', 'x64', '-DOD_BUILD_TESTING=OFF', '-DBUILD_TESTING=OFF',
    "-DOD_BUILD_NUMBER=$BuildNumber",
    "-DCMAKE_INSTALL_PREFIX=$taskRepo/build/windows/install",
    "-DPython_ROOT_DIR=$taskPythonCmakeRoot")
if ($taskMpJobs -gt 1) { $taskOptions += "-DBUILD_MP_JOBS=$taskMpJobs" }
Write-Output 'Checking the original project configuration with the installed prerequisites'
$ErrorActionPreference = 'Continue'
& cmake @taskOptions *> $taskConfigureLog
$ErrorActionPreference = 'Stop'
if ($LASTEXITCODE -ne 0) { Get-Content -LiteralPath $taskConfigureLog -Tail 60; throw "Project configuration failed; log: $taskConfigureLog" }
Write-Output 'Original project configuration succeeded'
& (Join-Path $PSScriptRoot 'prepare-windows-runtime.ps1')
