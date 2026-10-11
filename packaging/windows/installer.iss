; Inno Setup script for Icarus Server Mod Manager.
; Compile with:  ISCC.exe /DMyAppVersion=<version> packaging\windows\installer.iss
; Expects the PyInstaller onedir output at packaging\dist\IcarusServerModManager.

#ifndef MyAppVersion
#define MyAppVersion "0.0.0"
#endif

#define MyAppName "Icarus Server Mod Manager"
#define MyAppPublisher "Icarus Server Mod Manager"
#define MyAppExeName "IcarusServerModManager.exe"

[Setup]
AppId={{7A2C9E4B-5D31-4F87-9C42-6B8E1D2F3A55}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Icarus Server Mod Manager
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=IcarusServerModManagerSetup-{#MyAppVersion}
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\IcarusServerModManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
