#ifndef AppVersion
  #define AppVersion "0.7.3"
#endif
#ifndef Payload
  #define Payload "..\build\desktop\Read Docs"
#endif
[Setup]
AppId={{F3C46BAE-5B48-4ED2-9708-DA2DF12E740B}
AppName=Read Docs
AppVersion={#AppVersion}
AppPublisher=FRG
AppPublisherURL=https://frg.earth/read-docs
AppSupportURL=https://github.com/SproutSeeds/doc-reader/issues
DefaultDirName={localappdata}\Programs\Doc Reader
DefaultGroupName=Read Docs
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
#ifdef SignRelease
OutputBaseFilename=Read-Docs-{#AppVersion}-Windows-x64-Setup
SignTool=ReadDocs
SignedUninstaller=yes
#else
OutputBaseFilename=Read-Docs-{#AppVersion}-Windows-x64-UNSIGNED-Setup
#endif
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
Name: "{autoprograms}\Read Docs"; Filename: "{app}\DocReader.exe"
Name: "{autodesktop}\Read Docs"; Filename: "{app}\DocReader.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Run]
Filename: "{app}\DocReader.exe"; Description: "Open Read Docs"; Flags: nowait postinstall skipifsilent
[UninstallRun]
Filename: "{app}\DocReader.exe"; Parameters: "--stop"; Flags: runhidden waituntilterminated

[Code]
procedure MigrateLegacyShortcut(const LegacyPath, NewPath: String);
var
  Shell, Shortcut: Variant;
begin
  if not FileExists(LegacyPath) then Exit;
  try
    Shell := CreateOleObject('WScript.Shell');
    Shortcut := Shell.CreateShortcut(LegacyPath);
    // Keep unrelated shortcuts, even if their names happen to match.
    if CompareText(Shortcut.TargetPath, ExpandConstant('{app}\DocReader.exe')) <> 0 then Exit;
    if not FileExists(NewPath) then begin
      Shortcut := Shell.CreateShortcut(NewPath);
      Shortcut.TargetPath := ExpandConstant('{app}\DocReader.exe');
      Shortcut.WorkingDirectory := ExpandConstant('{app}');
      Shortcut.IconLocation := ExpandConstant('{app}\DocReader.exe,0');
      Shortcut.Description := 'Read Docs';
      Shortcut.Save;
    end;
    if FileExists(NewPath) then DeleteFile(LegacyPath);
  except
    Log('Could not migrate a legacy Read Docs shortcut.');
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    MigrateLegacyShortcut(ExpandConstant('{autoprograms}\Doc Reader.lnk'), ExpandConstant('{autoprograms}\Read Docs.lnk'));
    MigrateLegacyShortcut(ExpandConstant('{autodesktop}\Doc Reader.lnk'), ExpandConstant('{autodesktop}\Read Docs.lnk'));
  end;
end;
