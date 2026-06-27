@echo off
rem One-click build/package GUI (standalone pytauri; outputs .msi/.exe into build\)
rem
rem Outputs under project root build\:
rem   build\bundle-release\sse-gui.exe
rem   build\bundle-release\bundle\msi\*.msi
rem   build\bundle-release\bundle\nsis\*-setup.exe
rem
rem Prereqs: Rust MSVC + tauri-cli + uv + Node. First run auto-downloads python-build-standalone.
setlocal
cd /d "%~dp0.."

rem Kill any lingering sse-gui, else it locks pyembed DLLs and rebuild fails with os error 32
taskkill /IM sse-gui.exe /F >nul 2>&1

set "PYEXE=%CD%\src-tauri\pyembed\python\python.exe"

rem ---- add rustup/uv install dirs to PATH (common locations) ----
if exist "%USERPROFILE%\.cargo\bin" set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
if exist "%USERPROFILE%\.local\bin" set "PATH=%USERPROFILE%\.local\bin;%PATH%"

rem ---- check toolchain ----
where cargo >nul 2>&1
if errorlevel 1 echo [build-gui] cargo not found; install Rust MSVC and reopen terminal.
if errorlevel 1 exit /b 1
where uv >nul 2>&1
if errorlevel 1 echo [build-gui] uv not found; install uv from https://docs.astral.sh/uv/
if errorlevel 1 exit /b 1
where npm >nul 2>&1
if errorlevel 1 echo [build-gui] npm/Node not found; install Node.
if errorlevel 1 exit /b 1

rem ---- 1) frontend build ----
echo [build-gui] [1/4] building frontend, Vite to dist-frontend ...
pushd src\gui\frontend
call npm install --no-audit --no-fund
if errorlevel 1 goto :fe_fail
call npm run build
if errorlevel 1 goto :fe_fail
popd

rem ---- 2) prepare embedded Python (python-build-standalone) ----
echo [build-gui] [2/4] preparing embedded Python ...
set "PY_TAG=20260623"
set "PY_FILE=cpython-3.13.14+%PY_TAG%-x86_64-pc-windows-msvc-install_only_stripped.tar.gz"
if not exist "%PYEXE%" (
  echo   downloading python-build-standalone 3.13 msvc stripped ...
  if not exist src-tauri\pyembed mkdir src-tauri\pyembed
  curl -fL --retry 3 -o src-tauri\pyembed\py.tar.gz "https://github.com/astral-sh/python-build-standalone/releases/download/%PY_TAG%/%PY_FILE%"
  if errorlevel 1 echo [build-gui] download embedded Python failed
  if errorlevel 1 exit /b 1
  pushd src-tauri\pyembed
  tar xzf py.tar.gz
  del /f /q py.tar.gz
  popd
)
echo   embedded Python:
"%PYEXE%" --version

rem ---- 3) install project + sse_gui entry into embedded Python (non-editable, else paths break post-build) ----
echo [build-gui] [3/4] installing project into embedded Python ...
set "PYTAURI_STANDALONE=1"
uv pip install --python "%PYEXE%" --reinstall-package stock-save-editor .
if errorlevel 1 echo [build-gui] install project failed
if errorlevel 1 exit /b 1
uv pip install --python "%PYEXE%" --reinstall-package sse-gui .\src-tauri
if errorlevel 1 echo [build-gui] install sse-gui failed
if errorlevel 1 exit /b 1

rem ---- 4) tauri build ----
echo [build-gui] [4/4] tauri build release, output to build\ ...
set "PYO3_PYTHON=%PYEXE%"
pushd src-tauri
call cargo tauri build --config tauri.bundle.json -- --profile bundle-release
set "BUILD_EXIT=%ERRORLEVEL%"
popd

if not "%BUILD_EXIT%"=="0" echo [build-gui] tauri build failed
if not "%BUILD_EXIT%"=="0" exit /b %BUILD_EXIT%

echo.
echo [build-gui] done, outputs in build\bundle-release\ :
if exist build\bundle-release\sse-gui.exe echo   sse-gui.exe
for %%F in (build\bundle-release\bundle\msi\*.msi) do echo   %%~nxF
for %%F in (build\bundle-release\bundle\nsis\*.exe) do echo   %%~nxF
endlocal
exit /b 0

:fe_fail
popd
echo [build-gui] frontend build failed
endlocal
exit /b 1
