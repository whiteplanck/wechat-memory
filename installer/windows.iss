#define AppVersion "0.3.0"
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
MinVersion=10.0.18362
OutputDir=..\dist
OutputBaseFilename=WeChatMemory-Setup-{#AppVersion}-x64
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayName=WeChat Memory
UninstallDisplayIcon={app}\WeChatMemory.exe
SetupLogging=no

[Files]
Source: "..\build\windows-app\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: checkedonce

[Icons]
Name: "{group}\WeChat Memory"; Filename: "{app}\WeChatMemory.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\WeChat Memory"; Filename: "{app}\WeChatMemory.exe"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{group}\Initialize WeChat"; Filename: "{app}\runtime\python\python.exe"; Parameters: "-m wechat_memory.installer_launcher init"; WorkingDir: "{app}"
Name: "{group}\Instructions"; Filename: "{app}\WINDOWS-INSTALL.txt"
Name: "{group}\Uninstall WeChat Memory"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Installing Microsoft WebView2 Runtime (internet required)..."; Check: NeedsWebView; Flags: waituntilterminated
Filename: "{app}\WeChatMemory.exe"; WorkingDir: "{app}"; Description: "Launch WeChat Memory"; Flags: nowait postinstall skipifsilent

; No registry/PATH changes, startup tasks, or user-data deletion rules.

[Code]
function NeedsWebView: Boolean;
var Version: String;
begin
  Result := True;
  if RegQueryStringValue(HKLM32, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) then
    if (Version <> '') and (Version <> '0.0.0.0') then Result := False;
  if RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) then
    if (Version <> '') and (Version <> '0.0.0.0') then Result := False;
end;
