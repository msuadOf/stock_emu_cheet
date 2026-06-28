@echo off
rem Build standalone sse-tui.exe with PyInstaller (TUI = interactive terminal, stdlib-only).
rem
rem Output: build\pyi-dist\sse-tui.exe (single-file, runs without installing Python).
rem
rem Prereqs: Python 3.11+ with pip. First run auto-installs pyinstaller.
rem
rem Proxy (for pip install pyinstaller):
rem   scripts\build-tui.bat --proxy http://localhost:7888
rem   or set PROXY env var first.
setlocal EnableDelayedExpansion
cd /d "%~dp0.."

rem ---- parse --proxy <url> (also honors PROXY env var) ----
set "PROXY="
:parse
if "%~1"=="" goto :parsed
if /i "%~1"=="--proxy" (
  set "PROXY=%~2"
  shift
  shift
  goto :parse
)
shift
goto :parse
:parsed
set "PIP_PROXY="
if defined PROXY (
  echo [build-tui] using proxy: !PROXY!
  set "PIP_PROXY=--proxy !PROXY!"
)

rem ---- ensure pyinstaller ----
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
  echo [build-tui] installing pyinstaller ...
  python -m pip install !PIP_PROXY! pyinstaller
  if errorlevel 1 echo [build-tui] pip install pyinstaller failed
  if errorlevel 1 exit /b 1
)

rem ---- build sse-tui.exe (onefile, console) ----
echo [build-tui] building sse-tui.exe ...
python -m PyInstaller --onefile --console --name sse-tui ^
  --paths src --distpath build\pyi-dist --workpath build\pyi-work ^
  --specpath build\pyi-spec --noconfirm src\tui\frontend\app.py
if errorlevel 1 echo [build-tui] pyinstaller failed
if errorlevel 1 exit /b 1

echo.
echo [build-tui] done, output:
if exist build\pyi-dist\sse-tui.exe echo   build\pyi-dist\sse-tui.exe
endlocal
exit /b 0
