@echo off
rem One-click preview: CLI (non-interactive subcommand frontend)
rem Usage: scripts\run-cli.bat ^<subcommand^> [args...]
rem   scripts\run-cli.bat --help                       rem list all subcommands
rem   scripts\run-cli.bat list-saves -d "D:\saves"     rem list saves
rem   scripts\run-cli.bat set-pe 2001 5.0 --save x.sav --yes
setlocal
cd /d "%~dp0.."

set "PYTHONPATH=%CD%;%PYTHONPATH%"

echo [run-cli] starting CLI ...
python -m src.cli.cli %*
endlocal
