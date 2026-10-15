; Tạo file cài đặt WinRadar-Setup.exe bằng Inno Setup 6:
;   iscc /DAppVersion=1.0.0 packaging\winradar.iss
; Cần chạy PyInstaller trước để có thư mục dist\WinRadar.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6B0E2C1D-7A43-4C8E-9F1B-2D5A8E3C4B71}
AppName=WinRadar
AppVersion={#AppVersion}
AppPublisher=WinRadar
DefaultDirName={autopf}\WinRadar
DefaultGroupName=WinRadar
DisableProgramGroupPage=yes
; Cài cho riêng người dùng hiện tại -> không hỏi quyền Admin
PrivilegesRequired=lowest
OutputDir=..\Output
OutputBaseFilename=WinRadar-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=WinRadar
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Tạo biểu tượng WinRadar ngoài màn hình Desktop"; GroupDescription: "Biểu tượng:"

[Files]
Source: "..\dist\WinRadar\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\WinRadar\WinRadar"; Filename: "{app}\WinRadar.exe"
Name: "{autoprograms}\WinRadar\Đăng nhập Facebook"; Filename: "{app}\WinRadar.exe"; Parameters: "--login"
Name: "{autoprograms}\WinRadar\Xem demo (dữ liệu giả)"; Filename: "{app}\WinRadar.exe"; Parameters: "--demo"
Name: "{autoprograms}\WinRadar\Thư mục dữ liệu và proxy"; Filename: "{app}\WinRadar.exe"; Parameters: "--data"
Name: "{autoprograms}\WinRadar\Gỡ cài đặt WinRadar"; Filename: "{uninstallexe}"
Name: "{autodesktop}\WinRadar"; Filename: "{app}\WinRadar.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\WinRadar.exe"; Parameters: "--login"; Description: "Đăng nhập Facebook ngay (làm 1 lần)"; Flags: postinstall nowait skipifsilent
Filename: "{app}\WinRadar.exe"; Description: "Mở WinRadar"; Flags: postinstall nowait skipifsilent unchecked
