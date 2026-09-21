#define AppVersion "0.2.1"
[Setup]
AppId={{2D13F7F1-D846-4FB4-9919-48DAB16903E6}
AppName=WeChat Memory
AppVersion={#AppVersion}
AppPublisher=WeChat Memory Project
DefaultDirName={localappdata}\Programs\WeChatMemory
DefaultGroupName=WeChat Memory
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=WeChatMemory-Setup-{#AppVersion}-x64
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayName=WeChat Memory
SetupLogging=no

[Files]
Source: "..\build\windows-app\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: checkedonce

[Icons]
Name: "{group}\WeChat Memory"; Filename: "{app}\runtime\python\python.exe"; Parameters: "-m wechat_memory.server"; WorkingDir: "{app}"
Name: "{autodesktop}\WeChat Memory"; Filename: "{app}\runtime\python\python.exe"; Parameters: "-m wechat_memory.server"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{group}\Initialize WeChat"; Filename: "{app}\runtime\python\python.exe"; Parameters: "-m wechat_memory.installer_launcher init"; WorkingDir: "{app}"
Name: "{group}\Instructions"; Filename: "{app}\WINDOWS-INSTALL.txt"
Name: "{group}\Uninstall WeChat Memory"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\runtime\python\python.exe"; Parameters: "-m wechat_memory.server"; WorkingDir: "{app}"; Description: "Launch WeChat Memory"; Flags: nowait postinstall skipifsilent

; No registry/PATH changes, startup tasks, or user-data deletion rules.
