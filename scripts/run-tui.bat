@echo off
rem One-click preview: TUI (interactive terminal frontend)
rem Usage: scripts\run-tui.bat [save_dir]
rem   scripts\run-tui.bat                  rem default save dir
rem   scripts\run-tui.bat "D:\my\saves"    rem custom save dir
setlocal
cd /d "%~dp0.."

set "PYTHONPATH=%CD%;%PYTHONPATH%"

echo [run-tui] starting TUI ...
if "%~1"=="" (
  python -m src.tui.frontend.app
) else (
  python -m src.tui.frontend.app -d "%~1"
)
endlocal
