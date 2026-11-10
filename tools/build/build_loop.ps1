# Colosseum Heroes 64-bit build loop.
# 1. Unpacks D:\Projects\ColosseumHeroes64.zip to D:\Projects\ColosseumHeroes64 (first run only).
# 2. Runs a Unity batch build of the 64-bit APK, and again whenever build-request.txt changes,
#    so fixes can be applied and rebuilt without touching this window. Close the window to stop.
# Output: build-<n>.log and status.txt next to this script; APK in D:\Projects\ColosseumHeroes64\Builds.
# The editor runs windowed, not in -batchmode: Unity 2019.4 batch mode only accepts a legacy .ulf
# license file, which free Personal licenses no longer get; windowed it uses the Hub's license.
# A windowed editor does not quit by itself after compile or license errors, so the log is watched
# and the editor is closed when one of those appears.
# Everything this build writes stays on D: (C: is full): Unity's package cache is moved here from
# %LOCALAPPDATA%\Unity\cache, and Gradle, temp files and the project already live here.
# When this script file changes, the window reloads it between builds, so it never needs a restart.

$ErrorActionPreference = 'Stop'
$Tools    = Split-Path -Parent $MyInvocation.MyCommand.Path
$Proj     = 'D:\Projects\ColosseumHeroes64'
$Zip      = 'D:\Projects\ColosseumHeroes64.zip'
$UnityExe = 'D:\Unity 2019.4.41f2\Editor\Unity.exe'
$Request  = Join-Path $Tools 'build-request.txt'
$Status   = Join-Path $Tools 'status.txt'
$TimeoutMinutes = 120

# C: is nearly full, so Gradle's download cache and temp files go to D: (inherited by Unity and Gradle).
$env:GRADLE_USER_HOME = Join-Path $Tools 'gradle-home'
$env:TEMP = Join-Path $Tools 'temp'
$env:TMP  = $env:TEMP
New-Item -ItemType Directory -Force $env:GRADLE_USER_HOME, $env:TEMP | Out-Null

function Read-Shared([string]$Path) {
    try {
        $fs = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
        try { (New-Object IO.StreamReader($fs)).ReadToEnd() } finally { $fs.Dispose() }
    } catch { '' }
}

# Log lines after which a windowed editor would sit waiting forever.
$StuckPatterns = @(
    'Scripts have compiler errors',
    ': error CS',
    'executeMethod class',
    'executeMethod method',
    'has not been activated with a valid License',
    'No valid Unity Editor license',
    'Failed to activate/update license'
)

function Set-Status($text) {
    Set-Content $Status "$text $(Get-Date -Format s)"
    Write-Host "[$(Get-Date -Format HH:mm:ss)] $text"
}

# Unity Package Manager cache on D: (UPM_CACHE_ROOT, inherited by Unity), moving the C: one here.
$UpmCache = Join-Path $Tools 'unity-cache'
New-Item -ItemType Directory -Force $UpmCache | Out-Null
$env:UPM_CACHE_ROOT = $UpmCache
$OldUpmCache = Join-Path $env:LOCALAPPDATA 'Unity\cache'
if (Test-Path $OldUpmCache) {
    Set-Status "moving Unity's package cache from $OldUpmCache to $UpmCache"
    & robocopy.exe $OldUpmCache $UpmCache /E /MOVE /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { Write-Host "  robocopy exit code $LASTEXITCODE (Unity refills the cache on D: anyway)" }
}

if (-not (Test-Path (Join-Path $Proj 'Assets'))) {
    Set-Status 'unpacking project'
    & tar.exe -xf $Zip -C 'D:\Projects'
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path (Join-Path $Proj 'Assets'))) {
        Expand-Archive -Path $Zip -DestinationPath 'D:\Projects' -Force
    }
}
if (-not (Test-Path $Request)) { Set-Content $Request '1' }

$LastFile = Join-Path $Tools 'last-run.txt'
$last = ''
if (Test-Path $LastFile) { $last = (Get-Content $LastFile -Raw).Trim() }
$ScriptStamp = (Get-Item $PSCommandPath).LastWriteTimeUtc
Set-Status 'idle'
while ($true) {
    if ((Get-Item $PSCommandPath).LastWriteTimeUtc -ne $ScriptStamp) {
        Set-Status 'build window script updated, reloading'
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath
        exit $LASTEXITCODE
    }
    $want = ''
    try { $want = (Get-Content $Request -Raw -ErrorAction Stop).Trim() } catch { }
    if ($want -eq 'stop') { Set-Status 'stopped'; break }
    if ($want -and $want -ne $last) {
        $last = $want
        Set-Content $LastFile $want
        $id = ($want -split '\s+')[0]
        $log = Join-Path $Tools "build-$id.log"
        Set-Status "running $want"
        $mode = ''
        if (($want -split '\s+').Count -gt 1) { $mode = ($want -split '\s+')[1] }
        if ($mode -eq 'pack') {
            # Pack the project sources (no Library/Temp/Builds) and the build tools into one archive,
            # with a size report, so they can be uploaded to GitHub.
            $PackDir = Join-Path $Tools 'pack'
            New-Item -ItemType Directory -Force $PackDir | Out-Null
            $archive = Join-Path $PackDir "project-$id.tar.gz"
            $report = Join-Path $PackDir "sizes-$id.txt"
            try {
                $lines = @()
                foreach ($d in 'Assets', 'Packages', 'ProjectSettings', 'PortTools~') {
                    $p = Join-Path $Proj $d
                    if (Test-Path $p) {
                        $files = Get-ChildItem $p -Recurse -File -Force
                        $lines += "{0} files={1} bytes={2}" -f $d, $files.Count, (($files | Measure-Object Length -Sum).Sum)
                        $files | Where-Object { $_.Length -gt 50MB } | ForEach-Object { $lines += "BIG {0} {1}" -f $_.Length, $_.FullName }
                    }
                }
                Set-Content $report $lines
                $items = @('ColosseumHeroes64/Assets', 'ColosseumHeroes64/Packages', 'ColosseumHeroes64/ProjectSettings', 'ColosseumHeroes64/PortTools~',
                           'ColosseumHeroes64/README_64BIT_PORT.md', 'ColosseumHeroes64-tools/build_loop.ps1',
                           'ColosseumHeroes64-tools/setup_android.ps1', 'ColosseumHeroes64-tools/Start-Build.cmd')
                $items = $items | Where-Object { Test-Path (Join-Path 'D:\Projects' $_) }
                & tar.exe -czf $archive -C 'D:\Projects' @items 2>&1 | Out-File (Join-Path $Tools "build-$id.log")
                $a = Get-Item $archive
                Set-Status "done $id exit=$LASTEXITCODE pack=$([math]::Round($a.Length / 1MB, 1))MB"
            } catch {
                Set-Status "done $id exit=pack-failed $($_.Exception.Message)"
            }
            continue
        }
        if ($mode -eq 'play') {
            # Play-test: run the game in the editor, take screenshots into playtest\ and quit by itself.
            $unityArgs = "-accept-apiupdate -projectPath `"$Proj`" -buildTarget Android -executeMethod ColosseumHeroesPlayTest.Run -chPlayTestId $id -logFile `"$log`""
            $limit = 6
        } else {
            $unityArgs = "-quit -accept-apiupdate -projectPath `"$Proj`" -buildTarget Android -executeMethod ColosseumHeroesBuild.BuildApk -logFile `"$log`""
            $limit = $TimeoutMinutes
        }
        $p = Start-Process -FilePath $UnityExe -ArgumentList $unityArgs -PassThru
        $null = $p.Handle   # keeps ExitCode readable after the process ends
        $deadline = (Get-Date).AddMinutes($limit)
        $stuck = ''
        $stuckSince = $null
        while (-not $p.WaitForExit(10000)) {
            if ((Get-Date) -gt $deadline) { $stuck = 'timeout'; break }
            if (-not $stuckSince) {
                $text = Read-Shared $log
                foreach ($pat in $StuckPatterns) {
                    if ($text.Contains($pat)) { $stuckSince = Get-Date; $stuck = $pat; break }
                }
                if ($stuckSince) { Set-Status "running $id (saw '$stuck', closing the editor in 90 s unless it quits)" }
            } elseif (((Get-Date) - $stuckSince).TotalSeconds -ge 90) { break }
        }
        if (-not $p.HasExited) {
            # Ask the editor to close normally first: a hard kill can leave Library\ScriptAssemblies half-written.
            try { $null = $p.CloseMainWindow() } catch { }
            if (-not $p.WaitForExit(60000)) { Stop-Process -Id $p.Id -Force }
            Start-Sleep -Seconds 3
            Set-Status "done $id exit=closed ($stuck)"
        } else {
            $apk = Join-Path $Proj 'Builds\ColosseumHeroes-64bit.apk'
            $apkInfo = ''
            if (Test-Path $apk) { $a = Get-Item $apk; $apkInfo = " apk=$([math]::Round($a.Length / 1MB, 1))MB@$($a.LastWriteTime.ToString('s'))" }
            Set-Status "done $id exit=$($p.ExitCode)$apkInfo"
        }
    }
    Start-Sleep -Seconds 5
}
