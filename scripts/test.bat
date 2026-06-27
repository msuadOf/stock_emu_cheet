@echo off
rem Run tests directly (no build/compile). Shares the same code as the packaged app.
rem
rem Usage:
rem   scripts\test.bat                      rem full suite
rem   scripts\test.bat -v                   rem verbose
rem   scripts\test.bat tests.test_core_ops  rem single module
setlocal
cd /d "%~dp0.."

set "PYTHONPATH=%CD%;%PYTHONPATH%"
python run_tests.py %*
endlocal
