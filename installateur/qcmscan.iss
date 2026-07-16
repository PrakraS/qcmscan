; Installateur QCMScan (Inno Setup 6).
; Compilé par le workflow avec /DMyAppVersion=x.y.z
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

[Setup]
AppId={{C7D1A2E4-5F3B-4B8A-9C6D-2E7F1A0B3C4D}
AppName=QCMScan
AppVersion={#MyAppVersion}
AppPublisher=QCMScan
AppPublisherURL=https://github.com/PrakraS/qcmscan
DefaultDirName={autopf}\QCMScan
DisableProgramGroupPage=yes
; installation par-utilisateur : aucun droit administrateur requis
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=QCMScan-Setup
SetupIconFile=qcmscan.ico
UninstallDisplayIcon={app}\QCMScan.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
  GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\QCMScan\*"; DestDir: "{app}"; \
  Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\QCMScan"; Filename: "{app}\QCMScan.exe"
Name: "{autodesktop}\QCMScan"; Filename: "{app}\QCMScan.exe"; \
  Tasks: desktopicon

[Run]
Filename: "{app}\QCMScan.exe"; \
  Description: "{cm:LaunchProgram,QCMScan}"; \
  Flags: nowait postinstall skipifsilent
