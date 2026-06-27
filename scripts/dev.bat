@echo off
rem One-click dev preview (NO build/compile, instant). Shares src/core + backend with the packaged app.
rem
rem Usage:
rem   scripts\dev.bat tui [save_dir]             rem terminal frontend
rem   scripts\dev.bat cli ^<subcommand^> [args]  rem CLI frontend (e.g. --help / list-saves)
rem   scripts\dev.bat gui                        rem desktop frontend (pytauri-wheel, NO Rust!)
rem
rem dev and build (build-gui.bat) share the SAME src/core + src/gui/backend/commands.py + frontend;
rem edit once, both update. GUI dev uses pytauri-wheel (prebuilt, no Rust toolchain).
setlocal EnableDelayedExpansion
cd /d "%~dp0.."

if "%~1"=="" (
  echo Usage: scripts\dev.bat {tui^|cli^|gui} [args]
  exit /b 1
)
set "MODE=%~1"
shift

set "PYTHONPATH=%CD%;%PYTHONPATH%"

if /i "%MODE%"=="tui" (
  echo [dev] TUI mode ...
  if "%~1"=="" (
    python -m src.tui.frontend.app
  ) else (
    python -m src.tui.frontend.app -d "%~1"
  )
  goto :devend
)

if /i "%MODE%"=="cli" (
  echo [dev] CLI mode ...
  python -m src.cli.cli %*
  goto :devend
)

if /i "%MODE%"=="gui" goto :gui

echo [dev] unknown mode: %MODE% (choose tui^|cli^|gui)
exit /b 1

:gui
rem GUI wheel mode: no Rust, just pip install pytauri-wheel. Frontend uses vite dev (HMR).
set "VENV=%CD%\.venv"
set "FRONTEND=%CD%\src\gui\frontend"
where uv >nul 2>&1
if errorlevel 1 (
  echo [dev] uv required (pip install uv)
  exit /b 1
)

rem First time: auto-create venv + install pytauri-wheel + project
if not exist "%VENV%" (
  echo   first run: creating dev venv + installing pytauri-wheel ...
  uv venv --python-preference only-system
  uv pip install --python "%VENV%\Scripts\python.exe" "pytauri-wheel==0.8.*" -e .
)
if not exist "%FRONTEND%\node_modules" (
  echo   first run: installing frontend deps ...
  pushd "%FRONTEND%"
  call npm install --no-audit --no-fund
  popd
)

rem Start vite dev server (background, HMR)
echo [dev] starting Vite dev server (:5173, HMR) ...
start "vite-dev" /D "%FRONTEND%" cmd /c "npm run dev"
rem wait for vite to come up
timeout /t 4 /nobreak >nul

rem Run GUI in wheel mode (no Rust)
echo [dev] starting GUI (pytauri-wheel, no Rust compile) ...
set "DEV_SERVER=http://localhost:5173"
"%VENV%\Scripts\python.exe" -m src.gui.app_dev
set "GUI_EXIT=%ERRORLEVEL%"

rem On exit, kill the vite dev server (runs in a child window)
taskkill /FI "WINDOWTITLE eq vite-dev*" /F >nul 2>&1
rem Fallback: kill any node listening on 5173
for /f "tokens=5" %%P in ('netstat -ano -p tcp ^| findstr ":5173" ^| findstr "LISTENING"') do (
  taskkill /PID %%P /F >nul 2>&1
)
exit /b %GUI_EXIT%

:devend
endlocal
