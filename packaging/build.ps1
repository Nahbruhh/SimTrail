param(
    [string]$PythonExe = "",
    [switch]$SkipTestKit
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot

if (-not $PythonExe) {
    $preferred = Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"
    if (Test-Path -LiteralPath $preferred) {
        $PythonExe = $preferred
    } else {
        $PythonExe = (Get-Command python -ErrorAction Stop).Source
    }
}

Push-Location $projectRoot
try {
    & $PythonExe -m PyInstaller --noconfirm --clean ".\packaging\SimTrail.spec"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }

    $exe = Join-Path $projectRoot "dist\SimTrail.exe"
    if (-not (Test-Path -LiteralPath $exe)) {
        throw "Expected executable was not created: $exe"
    }

    if (-not $SkipTestKit) {
        $kit = Join-Path $projectRoot "dist\SimTrail-TestKit"
        if (Test-Path -LiteralPath $kit) {
            Remove-Item -LiteralPath $kit -Recurse -Force
        }
        New-Item -ItemType Directory -Path $kit | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $kit "connector") | Out-Null
        Copy-Item -LiteralPath $exe -Destination (Join-Path $kit "SimTrail.exe")
        Copy-Item -LiteralPath ".\packaging\START-HERE.txt" -Destination $kit
        Copy-Item -LiteralPath ".\LICENSE" -Destination $kit
        Copy-Item -LiteralPath ".\NOTICE" -Destination $kit
        Copy-Item -LiteralPath ".\THIRD_PARTY_NOTICES.md" -Destination $kit
        Copy-Item -LiteralPath ".\licenses" -Destination (Join-Path $kit "licenses") -Recurse
        Copy-Item -LiteralPath ".\ansys_extension\SimTrailConnector.xml" -Destination (Join-Path $kit "connector")
        Copy-Item -LiteralPath ".\ansys_extension\install_extension.ps1" -Destination (Join-Path $kit "connector")
        Copy-Item -LiteralPath ".\ansys_extension\README.md" -Destination (Join-Path $kit "connector")
        Copy-Item -LiteralPath ".\ansys_extension\SimTrailConnector" `
            -Destination (Join-Path $kit "connector\SimTrailConnector") -Recurse
        Get-ChildItem -LiteralPath (Join-Path $kit "connector") -Directory -Recurse `
            -Filter "__pycache__" | Remove-Item -Recurse -Force
        Get-ChildItem -LiteralPath (Join-Path $kit "connector") -File -Recurse `
            -Filter "*.pyc" | Remove-Item -Force

        $zip = Join-Path $projectRoot "dist\SimTrail-TestKit-0.1.0.zip"
        if (Test-Path -LiteralPath $zip) {
            Remove-Item -LiteralPath $zip -Force
        }
        Compress-Archive -Path (Join-Path $kit "*") -DestinationPath $zip
        Write-Host "Created test kit: $zip"
    }

    Write-Host "Created portable executable: $exe"
} finally {
    Pop-Location
}
