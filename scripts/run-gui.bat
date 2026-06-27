@echo off
rem One-click preview: GUI (dev mode: Vite HMR + tauri dev, hot reload)
rem
rem Prereqs (first time):
rem   pip install uv            rem skip if present
rem   uv venv ^&^& uv pip install -e ".[gui]" -e src-tauri   rem venv + pytauri + project
rem   cd src\gui\frontend ^&^& npm install ^&^& cd ..\..     rem frontend deps
rem   Also needs Rust(MSVC) + tauri-cli (see README)
rem
rem Usage: scripts\run-gui.bat
rem How it works:
rem   1) start Vite dev server (background, :5173, HMR)
rem   2) activate venv, set DEV_SERVER, run cargo tauri dev (loads dev server)
setlocal EnableDelayedExpansion
cd /d "%~dp0.."

set "VENV_DIR=%CD%\.venv"
set "FRONTEND=%CD%\src\gui\frontend"

rem ---- check prereqs ----
where cargo >nul 2>&1
if errorlevel 1 echo [run-gui] cargo not found; install Rust MSVC first.
if errorlevel 1 exit /b 1
if not exist "%VENV_DIR%" echo [run-gui] .venv not found; create it with uv first.
if not exist "%VENV_DIR%" exit /b 1
if not exist "%FRONTEND%\node_modules" echo [run-gui] frontend deps missing; run npm install in src\gui\frontend.
if not exist "%FRONTEND%\node_modules" exit /b 1

rem ---- activate venv ----
call "%VENV_DIR%\Scripts\activate.bat"
set "VIRTUAL_ENV=%VENV_DIR%"   rem main.rs uses this to locate the venv interpreter

rem ---- start Vite dev server (background) ----
echo [run-gui] starting Vite dev server (:5173, HMR) ...
start "vite-dev" /D "%FRONTEND%" cmd /c "npm run dev"
rem wait for Vite to come up
timeout /t 3 /nobreak >nul

rem ---- tauri dev ----
echo [run-gui] starting tauri dev (loads dev server) ...
set "DEV_SERVER=http://localhost:5173"
pushd src-tauri
call cargo tauri dev
set "TAURI_EXIT=%ERRORLEVEL%"
popd

rem kill vite on exit
taskkill /FI "WINDOWTITLE eq vite-dev*" /F >nul 2>&1
for /f "tokens=5" %%P in ('netstat -ano -p tcp ^| findstr ":5173" ^| findstr "LISTENING"') do (
  taskkill /PID %%P /F >nul 2>&1
)
endlocal
exit /b %TAURI_EXIT%
