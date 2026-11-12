@echo off
rem Đóng gói thành file .exe bằng PyInstaller (chạy trong thư mục dự án, đã kích hoạt venv)
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name TicketSystem main.py
rem Sao chép dữ liệu mẫu cạnh file .exe để chạy được ngay
if not exist dist\data mkdir dist\data
copy /Y data\*.json dist\data\ >nul
echo Xong. File chay: dist\TicketSystem.exe  (thu muc data nam canh file .exe)
pause
