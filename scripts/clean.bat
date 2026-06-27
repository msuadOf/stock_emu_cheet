@echo off
rem Clean build artifacts and deps (does not touch source or git-tracked files)
rem
rem Usage:
rem   scripts\clean.bat            rem clean standard artifacts
rem   scripts\clean.bat --deep     rem also nuke node_modules / .venv / pyembed
setlocal
cd /d "%~dp0.."

set "DEEP=0"
if /i "%~1"=="--deep" set "DEEP=1"

echo [clean] removing build artifacts ...

rem Rust/Tauri build output (incl. final .msi/.exe)
if exist "build" ( echo   removing build & rd /s /q "build" )
if exist "src-tauri\target" ( echo   removing src-tauri\target & rd /s /q "src-tauri\target" )

rem Frontend build output + TS incremental cache
if exist "src\gui\dist-frontend" ( echo   removing src\gui\dist-frontend & rd /s /q "src\gui\dist-frontend" )
if exist "src\gui\frontend\tsconfig.tsbuildinfo" ( echo   removing tsconfig.tsbuildinfo & del /f /q "src\gui\frontend\tsconfig.tsbuildinfo" )

rem tauri-generated intermediates
if exist "src-tauri\gen" ( echo   removing src-tauri\gen & rd /s /q "src-tauri\gen" )
if exist "src-tauri\WixTools" ( echo   removing src-tauri\WixTools & rd /s /q "src-tauri\WixTools" )
if exist "src-tauri\NSIS" ( echo   removing src-tauri\NSIS & rd /s /q "src-tauri\NSIS" )
if exist "src-tauri\nsis" ( echo   removing src-tauri\nsis & rd /s /q "src-tauri\nsis" )

rem Python bytecode caches (recursively remove all __pycache__, skip node_modules)
for /d /r . %%D in (__pycache__) do (
  echo %%D | findstr /C:"node_modules" >nul
  if errorlevel 1 (
    if exist "%%D" rd /s /q "%%D"
  )
)

if "%DEEP%"=="1" (
  echo [clean] --deep: also removing deps ...
  if exist "src\gui\frontend\node_modules" ( echo   removing node_modules & rd /s /q "src\gui\frontend\node_modules" )
  if exist ".venv" ( echo   removing .venv & rd /s /q ".venv" )
  if exist "src-tauri\pyembed" ( echo   removing src-tauri\pyembed & rd /s /q "src-tauri\pyembed" )
)

echo [clean] done
endlocal
