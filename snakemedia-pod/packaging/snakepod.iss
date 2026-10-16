; Tạo file cài đặt SnakemediaPOD-Setup.exe bằng Inno Setup 6:
;   iscc /DAppVersion=1.0.0 packaging\snakepod.iss
; Cần chạy PyInstaller trước để có thư mục dist\SnakemediaPOD.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6B0E2C1D-7A43-4C8E-9F1B-2D5A8E3C4B71}
AppName=SNAKEMEDIA POD
AppVersion={#AppVersion}
AppPublisher=SNAKEMEDIA POD
DefaultDirName={autopf}\SnakemediaPOD
DefaultGroupName=SNAKEMEDIA POD
DisableProgramGroupPage=yes
; Cài cho riêng người dùng hiện tại -> không hỏi quyền Admin
PrivilegesRequired=lowest
OutputDir=..\Output
OutputBaseFilename=SnakemediaPOD-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=SNAKEMEDIA POD
CloseApplications=yes

[Tasks]
Name: "startup"; Description: "Tự mở SNAKEMEDIA POD (thu nhỏ) khi bật máy, để tự quét mỗi đêm"; GroupDescription: "Tự quét:"
Name: "desktopicon"; Description: "Tạo biểu tượng SNAKEMEDIA POD ngoài màn hình Desktop"; GroupDescription: "Biểu tượng:"

[Files]
Source: "..\dist\SnakemediaPOD\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\SNAKEMEDIA POD\SNAKEMEDIA POD"; Filename: "{app}\SnakemediaPOD.exe"
Name: "{autoprograms}\SNAKEMEDIA POD\Đăng nhập Facebook"; Filename: "{app}\SnakemediaPOD.exe"; Parameters: "--login"
Name: "{autoprograms}\SNAKEMEDIA POD\Đăng nhập TikTok"; Filename: "{app}\SnakemediaPOD.exe"; Parameters: "--login tiktok"
Name: "{autoprograms}\SNAKEMEDIA POD\Xem demo (dữ liệu giả)"; Filename: "{app}\SnakemediaPOD.exe"; Parameters: "--demo"
Name: "{autoprograms}\SNAKEMEDIA POD\Thư mục dữ liệu và proxy"; Filename: "{app}\SnakemediaPOD.exe"; Parameters: "--data"
Name: "{autoprograms}\SNAKEMEDIA POD\Gỡ cài đặt SNAKEMEDIA POD"; Filename: "{uninstallexe}"
Name: "{autodesktop}\SNAKEMEDIA POD"; Filename: "{app}\SnakemediaPOD.exe"; Tasks: desktopicon
Name: "{userstartup}\SNAKEMEDIA POD"; Filename: "{app}\SnakemediaPOD.exe"; Parameters: "--no-browser"; Flags: runminimized; Tasks: startup

[Run]
Filename: "{app}\SnakemediaPOD.exe"; Parameters: "--login"; Description: "Đăng nhập Facebook ngay (làm 1 lần)"; Flags: postinstall nowait skipifsilent
Filename: "{app}\SnakemediaPOD.exe"; Description: "Mở SNAKEMEDIA POD"; Flags: postinstall nowait skipifsilent unchecked
