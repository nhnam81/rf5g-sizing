; ── rf5g-sizing Inno Setup Installer ──
; 5G NR RF Coverage Sizing Tool — Windows Installer
#define AppName "rf5g-sizing"
#define AppVersion "1.3.0"
#define AppPublisher "nhnam"
#define AppURL "https://github.com/nhnam/rf5g-sizing"

[Setup]
AppId={{RF5G-SIZING-2026-1.2.0}}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=..\dist
OutputBaseFilename=rf5g-sizing-{#AppVersion}-setup
Compression=lzma2/ultra64
SolidCompression=no
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\run_rf5g.bat

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; ── Embedded Python (pre-installed with all dependencies) ──
Source: "python-embed\*"; DestDir: "{app}\python"; Flags: ignoreversion recursesubdirs createallsubdirs

; ── Application ──
Source: "..\rf5g\*"; DestDir: "{app}\rf5g"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc"
Source: "..\pyproject.toml"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "run_rf5g.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: ".installed"; DestDir: "{app}"; Flags: ignoreversion

; ── Documentation ──
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\INSTALL_GUIDE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\USER_GUIDE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\run_rf5g.bat"; WorkingDir: "{app}"
Name: "{group}\User Guide"; Filename: "{app}\USER_GUIDE.md"
Name: "{group}\Install Guide"; Filename: "{app}\INSTALL_GUIDE.md"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\run_rf5g.bat"; Tasks: desktopicon; WorkingDir: "{app}"

[Run]
Filename: "{app}\run_rf5g.bat"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\python\Scripts"
Type: filesandordirs; Name: "{app}\python\Lib\site-packages"
Type: files; Name: "{app}\.installed"
Type: filesandordirs; Name: "{app}\rf5g\__pycache__"
Type: filesandordirs; Name: "{app}\rf5g\engine\__pycache__"
Type: filesandordirs; Name: "{app}\rf5g\models\__pycache__"
Type: filesandordirs; Name: "{app}\rf5g\viz\__pycache__"
Type: filesandordirs; Name: "{app}\rf5g\web\__pycache__"