@echo off
setlocal
cd /d "%~dp0.."

if exist "public\brand\quanthire-logo-source.png" goto run
if exist "C:\Users\prakumar\.cursor\projects\d-QuantHire-AI\assets\quanthire-logo-source.png" (
  copy /Y "C:\Users\prakumar\.cursor\projects\d-QuantHire-AI\assets\quanthire-logo-source.png" "public\brand\quanthire-logo-source.png"
  goto run
)
if exist "C:\Users\prakumar\.cursor\projects\d-QuantHire-AI\assets\c__Users_prakumar_AppData_Roaming_Cursor_User_workspaceStorage_486f2694f1bdf0b8cca5595157957c1f_images_ChatGPT_Image_Aug_17__2026__05_04_01_PM__1_-cf538ae5-33eb-4618-9ec3-4f63e9736b12.png" (
  copy /Y "C:\Users\prakumar\.cursor\projects\d-QuantHire-AI\assets\c__Users_prakumar_AppData_Roaming_Cursor_User_workspaceStorage_486f2694f1bdf0b8cca5595157957c1f_images_ChatGPT_Image_Aug_17__2026__05_04_01_PM__1_-cf538ae5-33eb-4618-9ec3-4f63e9736b12.png" "public\brand\quanthire-logo-source.png"
  goto run
)
echo Copy the official logo to public\brand\quanthire-logo-source.png and re-run.
exit /b 1

:run
python scripts\setup-brand-assets.py
if errorlevel 1 exit /b 1

echo.
echo Done. Generated assets in public\brand\ and favicon files.
dir /b public\brand\quanthire*.png
exit /b 0
