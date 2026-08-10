#define MyAppName "SimTrail"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "SimTrail"
#define MyAppExeName "SimTrail.exe"

[Setup]
AppId={{6651CBF0-9C14-4CB8-9152-F93DBD3060AC}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\SimTrail
DefaultGroupName=SimTrail
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=SimTrail-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=..\LICENSE

[Files]
Source: "..\dist\SimTrail.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\NOTICE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs
Source: "..\ansys_extension\SimTrailConnector.xml"; DestDir: "{app}\connector"; Flags: ignoreversion
Source: "..\ansys_extension\install_extension.ps1"; DestDir: "{app}\connector"; Flags: ignoreversion
Source: "..\ansys_extension\README.md"; DestDir: "{app}\connector"; Flags: ignoreversion
Source: "..\ansys_extension\SimTrailConnector\*"; DestDir: "{app}\connector\SimTrailConnector"; Excludes: "__pycache__\*;*.pyc"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{autoprograms}\SimTrail"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\SimTrail"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "connectorv242"; Description: "Install the Workbench 2024 R2 connector"; GroupDescription: "Ansys integration:"

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\connector\install_extension.ps1"" -AnsysVersion v242"; Description: "Install the Workbench 2024 R2 connector"; Flags: postinstall skipifsilent; Tasks: connectorv242
Filename: "{app}\{#MyAppExeName}"; Description: "Launch SimTrail"; Flags: nowait postinstall skipifsilent
