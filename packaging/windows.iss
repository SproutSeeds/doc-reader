#ifndef AppVersion
  #define AppVersion "0.6.1"
#endif
#ifndef Payload
  #define Payload "..\build\desktop\Doc Reader"
#endif
[Setup]
AppId={{F3C46BAE-5B48-4ED2-9708-DA2DF12E740B}
AppName=Doc Reader
AppVersion={#AppVersion}
AppPublisher=FRG
AppPublisherURL=https://frg.earth/read-docs
AppSupportURL=https://github.com/SproutSeeds/doc-reader/issues
DefaultDirName={localappdata}\Programs\Doc Reader
DefaultGroupName=Doc Reader
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputBaseFilename=Doc-Reader-{#AppVersion}-Windows-x64-Setup
OutputDir=..\dist
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\doc-reader.ico
UninstallDisplayIcon={app}\DocReader.exe
LicenseFile=..\LICENSE
CloseApplications=yes
[Files]
Source: "{#Payload}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{autoprograms}\Doc Reader"; Filename: "{app}\DocReader.exe"
Name: "{autodesktop}\Doc Reader"; Filename: "{app}\DocReader.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Run]
Filename: "{app}\DocReader.exe"; Description: "Open Doc Reader"; Flags: nowait postinstall skipifsilent
[UninstallRun]
Filename: "{app}\DocReader.exe"; Parameters: "--stop"; Flags: runhidden waituntilterminated
