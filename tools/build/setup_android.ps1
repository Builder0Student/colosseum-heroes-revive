# Colosseum Heroes 64-bit build: installs Unity 2019.4.41f2 (the first 2019.4 release a free
# Personal license can activate) with Android Build Support (the same parts Unity Hub installs:
# Android player, SDK, NDK r19, JDK 8), plus Unity Hub for signing in. Everything goes to D:.
# Runs elevated because Unity's installers need administrator rights.
# Log: setup.log next to this script.

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Script = $MyInvocation.MyCommand.Path
$Tools  = Split-Path -Parent $Script
$Log    = Join-Path $Tools 'setup.log'
$Unity  = 'D:\Unity 2019.4.41f2'
$HubDir = 'D:\Unity Hub'
$AP     = Join-Path $Unity 'Editor\Data\PlaybackEngines\AndroidPlayer'
$SDK    = Join-Path $AP 'SDK'
$DL     = Join-Path $Tools 'downloads'

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-AndroidReady {
    (Test-Path (Join-Path $Unity 'Editor\Unity.exe')) -and
    (Test-Path (Join-Path $HubDir 'Unity Hub.exe')) -and
    (Test-Path (Join-Path $AP 'Variations\il2cpp')) -and
    (Test-Path (Join-Path $AP 'OpenJDK\bin\java.exe')) -and
    (Test-Path (Join-Path $AP 'NDK\source.properties')) -and
    (Test-Path (Join-Path $SDK 'tools\bin\sdkmanager.bat')) -and
    (Test-Path (Join-Path $SDK 'platform-tools\adb.exe')) -and
    (Test-Path (Join-Path $SDK 'build-tools\30.0.2\aapt.exe')) -and
    (Test-Path (Join-Path $SDK 'platforms\android-30\android.jar'))
}

if (Test-AndroidReady) {
    Add-Content $Log "$(Get-Date -Format s) Android Build Support already complete."
    exit 0
}

if (-not (Test-Admin)) {
    Write-Host 'Asking Windows for administrator rights (click Yes)...'
    try {
        $p = Start-Process powershell.exe -Verb RunAs -Wait -PassThru -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$Script`""
        exit $p.ExitCode
    } catch {
        Add-Content $Log "$(Get-Date -Format s) ERROR administrator prompt declined or failed: $_"
        Write-Host 'Administrator rights were not granted.' -ForegroundColor Red
        exit 2
    }
}

Start-Transcript -Path $Log -Append | Out-Null
function Step($m) { Write-Host ''; Write-Host "=== $m" -ForegroundColor Cyan }

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    New-Item -ItemType Directory -Force $DL | Out-Null

    Step 'Diagnostics'
    foreach ($d in 'C', 'D') {
        $drive = Get-PSDrive $d -ErrorAction SilentlyContinue
        if ($drive) { Write-Host ("Drive {0}: {1:N1} GB free" -f $d, ($drive.Free / 1GB)) }
    }
    Write-Host ("Unity legacy license file: {0}" -f (Test-Path 'C:\ProgramData\Unity\Unity_lic.ulf'))
    Write-Host ("Unity licensing client folder: {0}" -f (Test-Path (Join-Path $env:LOCALAPPDATA 'Unity\licenses')))
    Write-Host ("Unity Hub installed: {0}" -f ((Test-Path (Join-Path $env:ProgramFiles 'Unity Hub\Unity Hub.exe')) -or (Test-Path (Join-Path $env:LOCALAPPDATA 'Programs\Unity Hub\Unity Hub.exe'))))
    $curl = (Get-Command curl.exe -ErrorAction SilentlyContinue)
    $tar  = (Get-Command tar.exe -ErrorAction SilentlyContinue)
    Write-Host ("curl.exe: {0}" -f $(if ($curl) { $curl.Source } else { 'missing' }))
    Write-Host ("tar.exe: {0}" -f $(if ($tar) { $tar.Source } else { 'missing' }))
    if (-not $curl) { throw 'curl.exe is missing (Windows 10 1803 or newer includes it).' }

    function Get-File([string]$Url, [string]$Name, [long]$MinBytes, [string]$Sha256) {
        $out = Join-Path $DL $Name
        $done = "$out.ok"
        if ((Test-Path $done) -and (Test-Path $out)) { Write-Host "already downloaded: $Name"; return $out }
        Write-Host "downloading $Name"
        Write-Host "  from $Url"
        # Connection resets (curl exit 56) happen on this network; each attempt resumes the partial
        # file (-C -), so allow up to 10 attempts. HTTP errors (22, e.g. 404) give up after 3.
        for ($try = 1; $try -le 10; $try++) {
            & curl.exe --ssl-revoke-best-effort -L --fail --retry 5 --retry-delay 5 --progress-bar -C - -o $out $Url
            $code = $LASTEXITCODE
            if ($code -eq 0) { break }
            Write-Host "  curl exit code $code (attempt $try)"
            if ($try -eq 10 -or ($code -eq 22 -and $try -ge 3)) { throw "download failed: $Url" }
            if ($code -eq 33 -or $code -eq 22) { Remove-Item $out -Force -ErrorAction SilentlyContinue }
            Start-Sleep -Seconds 10
        }
        $len = (Get-Item $out).Length
        Write-Host ("  {0:N1} MB" -f ($len / 1MB))
        if ($len -lt $MinBytes) { Remove-Item $out -Force; throw "download too small ($len bytes): $Name" }
        if ($Sha256) {
            $h = (Get-FileHash $out -Algorithm SHA256).Hash.ToLower()
            if ($h -ne $Sha256.ToLower()) { Remove-Item $out -Force; throw "checksum mismatch for $Name" }
            Write-Host '  SHA-256 verified'
        }
        Set-Content $done 'ok'
        return $out
    }

    # Downloads one Android archive from several sources, resuming the same partial file across
    # them (they serve identical bytes), and keeps it only if its exact size and SHA-1 match Google's
    # published values. A source that stalls (under 10 KB/s for 60 s) is left for the next one; what it
    # downloaded is kept. Up to 30 rounds with 20 s pauses ride out connection drops; the last round
    # has no speed limit.
    function Get-Verified([string]$RemoteName, [string]$Name, [long]$Size, [string]$Sha1, [switch]$GoogleOnly) {
        $out = Join-Path $DL $Name
        $done = "$out.ok"
        if ((Test-Path $done) -and (Test-Path $out)) { Write-Host "already downloaded: $Name"; return $out }
        $sources = @("https://dl.google.com/android/repository/$RemoteName")
        if (-not $GoogleOnly) {
            $sources += "https://mirrors.cloud.tencent.com/AndroidSDK/$RemoteName"
            $sources += "https://mirrors.neusoft.edu.cn/android/repository/$RemoteName"
        }
        Write-Host ("downloading {0} ({1:N1} MB)" -f $Name, ($Size / 1MB))
        $rounds = 30
        :rounds for ($round = 1; $round -le $rounds; $round++) {
            foreach ($u in $sources) {
                $have = 0
                if (Test-Path $out) { $have = (Get-Item $out).Length }
                if ($have -gt $Size) { Write-Host '  partial file is larger than expected, starting over'; Remove-Item $out -Force; $have = 0 }
                if ($have -lt $Size) {
                    $limit = @('--speed-limit', '10240', '--speed-time', '60')
                    if ($round -eq $rounds) { $limit = @() }
                    Write-Host ("  {0:N1} of {1:N1} MB, trying {2}" -f ($have / 1MB), ($Size / 1MB), ([uri]$u).Host)
                    & curl.exe --ssl-revoke-best-effort -L --fail --connect-timeout 20 --progress-bar @limit -C - -o $out $u
                    $code = $LASTEXITCODE
                    if ($code -ne 0) {
                        Write-Host "  curl exit code $code from $(([uri]$u).Host)"
                        if ($code -eq 33) { Remove-Item $out -Force -ErrorAction SilentlyContinue }
                        continue
                    }
                }
                if ((Test-Path $out) -and (Get-Item $out).Length -eq $Size) {
                    $h = (Get-FileHash $out -Algorithm SHA1).Hash.ToLower()
                    if ($Sha1 -and $h -ne $Sha1.ToLower()) {
                        Write-Host "  SHA-1 mismatch ($h), deleting and starting over"
                        Remove-Item $out -Force
                        continue
                    }
                    if ($Sha1) { Write-Host '  size and SHA-1 verified' } else { Write-Host '  size verified' }
                    Set-Content $done 'ok'
                    return $out
                }
            }
            Write-Host "  round $round of $rounds done, waiting 20 s for the connection"
            Start-Sleep -Seconds 20
        }
        throw "download failed after $rounds rounds: $Name"
    }

    # Extracts a zip whose content is a single top-level folder and moves that folder to $Target.
    function Install-Zip([string]$Zip, [string]$Target) {
        $tmp = Join-Path $AP '__extract'
        if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
        New-Item -ItemType Directory -Force $tmp | Out-Null
        Write-Host "extracting $(Split-Path -Leaf $Zip)"
        $ok = $false
        if ($tar) {
            & tar.exe -xf $Zip -C $tmp
            $ok = ($LASTEXITCODE -eq 0)
            if (-not $ok) { Write-Host "  tar.exe exit code $LASTEXITCODE, retrying with Expand-Archive"; Remove-Item $tmp -Recurse -Force; New-Item -ItemType Directory -Force $tmp | Out-Null }
        }
        if (-not $ok) { Expand-Archive -Path $Zip -DestinationPath $tmp -Force }
        $items = @(Get-ChildItem $tmp -Force)
        if ($items.Count -ne 1 -or -not $items[0].PSIsContainer) { throw "unexpected layout in $Zip : $($items.Name -join ', ')" }
        if (Test-Path $Target) { Remove-Item $Target -Recurse -Force }
        New-Item -ItemType Directory -Force (Split-Path -Parent $Target) | Out-Null
        Move-Item $items[0].FullName $Target
        Remove-Item $tmp -Recurse -Force
        Write-Host "  -> $Target"
    }

    function Install-Exe([string]$Exe, [string]$Dir, [string]$Check) {
        $sig = Get-AuthenticodeSignature $Exe
        Write-Host ("  signature: {0}, signer: {1}" -f $sig.Status, $sig.SignerCertificate.Subject)
        if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'Unity') { throw "$(Split-Path -Leaf $Exe) is not validly signed by Unity" }
        Write-Host '  installing (takes a few minutes)...'
        $p = Start-Process -FilePath $Exe -ArgumentList "/S /D=$Dir" -Wait -PassThru
        Write-Host "  installer exit code $($p.ExitCode)"
        if (-not (Test-Path $Check)) { throw "$(Split-Path -Leaf $Exe) did not install" }
    }

    Step 'Unity Editor 2019.4.41f2'
    if (-not (Test-Path (Join-Path $Unity 'Editor\Unity.exe'))) {
        $exe = Get-File 'https://download.unity3d.com/download_unity/6b23d448b533/Windows64EditorInstaller/UnitySetup64-2019.4.41f2.exe' 'UnitySetup64-2019.4.41f2.exe' 1850000000 ''
        Install-Exe $exe $Unity (Join-Path $Unity 'Editor\Unity.exe')
    } else { Write-Host 'already installed' }

    Step 'Unity Hub (for signing in and the free Personal license)'
    if (-not (Test-Path (Join-Path $HubDir 'Unity Hub.exe'))) {
        # The old fixed name (hub/prod/UnityHubSetup.exe) now returns an HTTP error. Unity publishes
        # versioned installers instead (hub/prod/<ver>/UnityHubSetup-<ver>-x64.exe); try newest first.
        # Each URL downloads to its own file name, so a partial file is never resumed from another URL.
        $hubUrls = @(
            'https://public-cdn.cloud.unity3d.com/hub/prod/UnityHubSetup-x64.exe',
            'https://public-cdn.cloud.unity3d.com/hub/prod/3.22.4/UnityHubSetup-3.22.4-x64.exe',
            'https://public-cdn.cloud.unity3d.com/hub/prod/3.21.2/UnityHubSetup-3.21.2-x64.exe',
            'https://public-cdn.cloud.unity3d.com/hub/prod/3.21.0/UnityHubSetup-3.21.0-x64.exe',
            'https://public-cdn.cloud.unity3d.com/hub/prod/3.20.0/UnityHubSetup-3.20.0-x64.exe',
            'https://public-cdn.cloud.unity3d.com/hub/prod/3.19.5/UnityHubSetup-3.19.5-x64.exe'
        )
        $exe = $null
        foreach ($u in $hubUrls) {
            try { $exe = Get-File $u ([IO.Path]::GetFileName($u)) 50000000 ''; break }
            catch { Write-Host "  not available, trying the next address" }
        }
        if (-not $exe) { throw 'Unity Hub installer was not found at any known address' }
        Install-Exe $exe $HubDir (Join-Path $HubDir 'Unity Hub.exe')
    } else { Write-Host 'already installed' }

    Step 'Android Build Support (Unity player for Android)'
    if (-not (Test-Path (Join-Path $AP 'Variations\il2cpp'))) {
        $exe = Get-File 'https://download.unity3d.com/download_unity/6b23d448b533/TargetSupportInstaller/UnitySetup-Android-Support-for-Editor-2019.4.41f2.exe' 'UnitySetup-Android-Support-for-Editor-2019.4.41f2.exe' 340000000 ''
        Install-Exe $exe $Unity (Join-Path $AP 'Variations\il2cpp')
    } else { Write-Host 'already installed' }

    Step 'JDK 8 (Eclipse Temurin, current certificates)'
    if (-not (Test-Path (Join-Path $AP 'OpenJDK\bin\java.exe'))) {
        $jdk = $null
        # 1. Adoptium's API for the newest JDK 8 zip (with its SHA-256). Checked before use: an empty
        #    answer previously led to curl being called with no URL.
        try {
            $api = 'https://api.adoptium.net/v3/assets/latest/8/hotspot?architecture=x64&image_type=jdk&os=windows&vendor=eclipse'
            $raw = (& curl.exe --ssl-revoke-best-effort -sSL --fail --retry 3 $api | Out-String)
            if ($LASTEXITCODE -ne 0) { throw "curl exit code $LASTEXITCODE" }
            if (-not $raw.Trim()) { throw 'empty answer' }
            $assets = @($raw | ConvertFrom-Json) | ForEach-Object { $_ }
            $pkg = @($assets | Where-Object { $_.binary.package.link -like '*.zip' } | ForEach-Object { $_.binary.package })[0]
            if (-not $pkg -or -not $pkg.link) { throw 'no zip package in the answer' }
            $jdk = Get-File $pkg.link $pkg.name 90000000 $pkg.checksum
        } catch { Write-Host "  Adoptium API route failed: $_" }
        # 2. Fixed Temurin releases on GitHub, verified with the .sha256.txt published beside each zip.
        if (-not $jdk) {
            foreach ($tag in 'jdk8u492-b09', 'jdk8u482-b08') {
                $ver  = ($tag -replace '^jdk', '') -replace '-', ''
                $name = "OpenJDK8U-jdk_x64_windows_hotspot_$ver.zip"
                $url  = "https://github.com/adoptium/temurin8-binaries/releases/download/$tag/$name"
                try {
                    $sumText = (& curl.exe --ssl-revoke-best-effort -sSL --fail --retry 3 "$url.sha256.txt" | Out-String)
                    if ($LASTEXITCODE -ne 0) { throw "checksum file: curl exit code $LASTEXITCODE" }
                    $sum = ($sumText.Trim() -split '\s+')[0]
                    if ($sum -notmatch '^[0-9a-fA-F]{64}$') { throw 'checksum file does not hold a SHA-256' }
                    $jdk = Get-File $url $name 90000000 $sum
                    break
                } catch { Write-Host "  $tag failed: $_" }
            }
        }
        if (-not $jdk) { throw 'could not download JDK 8 from Adoptium or GitHub' }
        Install-Zip $jdk (Join-Path $AP 'OpenJDK')
    } else { Write-Host 'already installed' }
    Get-Content (Join-Path $AP 'OpenJDK\release') -ErrorAction SilentlyContinue | Select-String 'JAVA_VERSION|IMPLEMENTOR' | ForEach-Object { Write-Host "  $_" }

    Step 'Android SDK'
    # Sizes and SHA-1s are Google's published values (Android SDK repository metadata).
    # platform-tools r28.0.1 is no longer listed there, so it comes from Google only, checked by size range.
    $sdkParts = @(
        @{ Remote = 'sdk-tools-windows-4333796.zip';      Name = 'sdk-tools-windows-4333796.zip';      Size = 156136858; Sha1 = 'aa298b5346ee0d63940d13609fe6bec621384510'; Target = 'tools';                Check = 'tools\bin\sdkmanager.bat' },
        @{ Remote = 'efbaa277338195608aa4e3dbd43927e97f60218c.build-tools_r30.0.2-windows.zip'; Name = 'build-tools_r30.0.2-windows.zip'; Size = 53783318; Sha1 = 'b42b77e02b82f242432cd7ffff5cbb92f6888ca7'; Target = 'build-tools\30.0.2'; Check = 'build-tools\30.0.2\aapt.exe' },
        @{ Remote = 'platform-30_r03.zip';                Name = 'platform-30_r03.zip';                Size = 52328361;  Sha1 = 'e7c6280901dcfa511af098d67dd88c4dfcbc6ea2'; Target = 'platforms\android-30'; Check = 'platforms\android-30\android.jar' }
    )
    foreach ($part in $sdkParts) {
        if (Test-Path (Join-Path $SDK $part.Check)) { Write-Host "already installed: $($part.Target)"; continue }
        $z = Get-Verified $part.Remote $part.Name $part.Size $part.Sha1
        Install-Zip $z (Join-Path $SDK $part.Target)
    }
    if (-not (Test-Path (Join-Path $SDK 'platform-tools\adb.exe'))) {
        $z = Get-File 'https://dl.google.com/android/repository/platform-tools_r28.0.1-windows.zip' 'platform-tools_r28.0.1-windows.zip' 4000000 ''
        Install-Zip $z (Join-Path $SDK 'platform-tools')
    } else { Write-Host 'already installed: platform-tools' }
    # Android SDK license, accepted by the user in chat (same text Unity Hub / Android Studio show).
    $lic = Join-Path $SDK 'licenses'
    New-Item -ItemType Directory -Force $lic | Out-Null
    Set-Content (Join-Path $lic 'android-sdk-license') "`n24333f8a63b6825ea9c5514f83c2829b004d1fee`nd56f5187479451eabf01fb78af6dfcb131a6481e`n8933bad161af4178b1185d1a37fbf41ea5269c55" -NoNewline

    Step 'Android NDK r19'
    if (-not (Test-Path (Join-Path $AP 'NDK\source.properties'))) {
        $ndk = Get-Verified 'android-ndk-r19-windows-x86_64.zip' 'android-ndk-r19-windows-x86_64.zip' 795986424 '37906e8e79a9dddf6805325f706a072055e4136c'
        Install-Zip $ndk (Join-Path $AP 'NDK')
    } else { Write-Host 'already installed' }
    Get-Content (Join-Path $AP 'NDK\source.properties')

    if (-not (Test-AndroidReady)) { throw 'some Android parts are still missing' }
    Step 'Cleaning up downloads'
    Remove-Item $DL -Recurse -Force
    Step 'Unity 2019.4.41f2, Unity Hub and Android Build Support are ready'
    Stop-Transcript | Out-Null
    exit 0
} catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
    Write-Host $_.ScriptStackTrace
    Stop-Transcript | Out-Null
    Start-Sleep 5
    exit 1
}
