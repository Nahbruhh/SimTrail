param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^v\d{3}$')]
    [string]$AnsysVersion,
    [switch]$Uninstall
)

$sourceFolder = Join-Path $PSScriptRoot "SimTrailConnector"
$sourceXml = Join-Path $PSScriptRoot "SimTrailConnector.xml"
$targetRoot = Join-Path $env:APPDATA "Ansys\$AnsysVersion\ACT\extensions"
$targetFolder = Join-Path $targetRoot "SimTrailConnector"
$targetXml = Join-Path $targetRoot "SimTrailConnector.xml"

if ($Uninstall) {
    if (Test-Path -LiteralPath $targetFolder) {
        Remove-Item -LiteralPath $targetFolder -Recurse -Force
    }
    if (Test-Path -LiteralPath $targetXml) {
        Remove-Item -LiteralPath $targetXml -Force
        Write-Host "Removed SimTrailConnector from $targetRoot"
    } else {
        Write-Host "SimTrailConnector XML is not installed at $targetXml"
    }
    exit 0
}

if (-not (Test-Path -LiteralPath $sourceFolder) -or -not (Test-Path -LiteralPath $sourceXml)) {
    throw "Extension source must contain SimTrailConnector.xml and the SimTrailConnector folder."
}

New-Item -ItemType Directory -Path $targetRoot -Force | Out-Null
if (Test-Path -LiteralPath $targetFolder) {
    Remove-Item -LiteralPath $targetFolder -Recurse -Force
}
if (Test-Path -LiteralPath $targetXml) {
    Remove-Item -LiteralPath $targetXml -Force
}
Copy-Item -LiteralPath $sourceXml -Destination $targetXml
Copy-Item -LiteralPath $sourceFolder -Destination $targetFolder -Recurse
Get-ChildItem -LiteralPath $targetFolder -Directory -Recurse -Filter "__pycache__" |
    Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $targetFolder -File -Recurse -Filter "*.pyc" |
    Remove-Item -Force
Write-Host "Installed SimTrailConnector XML and folder to $targetRoot"
Write-Host "Restart Workbench, open Extensions > Manage Extensions, and enable SimTrailConnector."
