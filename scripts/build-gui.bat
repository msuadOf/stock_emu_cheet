@echo off
rem One-click build/package GUI (standalone pytauri; outputs .msi/.exe into build\)
rem
rem Outputs under project root build\:
rem   build\bundle-release\sse-gui.exe
rem   build\bundle-release\bundle\msi\*.msi
rem   build\bundle-release\bundle\nsis\*-setup.exe
rem
rem Prereqs: Rust MSVC + tauri-cli + uv + Node. First run auto-downloads python-build-standalone.
rem
rem Proxy (for downloads: python-build-standalone via curl, npm/uv/cargo deps):
rem   scripts\build-gui.bat --proxy http://localhost:7888
rem   or set PROXY env var first:  set PROXY=http://localhost:7888
rem   Applies --proxy to curl and exports HTTP_PROXY/HTTPS_PROXY for npm/uv/cargo.
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
if defined PROXY (
  echo [build-gui] using proxy: !PROXY!
  set "HTTP_PROXY=!PROXY!"
  set "HTTPS_PROXY=!PROXY!"
  set "CURL_PROXY=--proxy !PROXY!"
) else (
  set "CURL_PROXY="
)

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
  curl -fL --retry 3 !CURL_PROXY! -o src-tauri\pyembed\py.tar.gz "https://github.com/astral-sh/python-build-standalone/releases/download/%PY_TAG%/%PY_FILE%"
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

rem ---- 5) portable.zip: sse-gui.exe + pyembed/python/ (extract and run, no install) ----
echo [build-gui] [5/5] packing portable.zip ...
rem read version from tauri.conf.json (CI Sync version step has written it)
for /f "delims=" %%V in ('""%PYEXE%" -c "import json;print(json.load(open(r'src-tauri/tauri.conf.json',encoding='utf-8'))['version'])""') do set "APPVER=%%V"
set "PORTABLE_ZIP=build\bundle-release\StocksSaveEditor-%APPVER%-portable.zip"
set "STAGE=build\portable-stage"
if exist "%STAGE%" rd /s /q "%STAGE%"
mkdir "%STAGE%"
copy /y build\bundle-release\sse-gui.exe "%STAGE%\sse-gui.exe" >nul
rem Flatten pyembed/python CONTENTS into STAGE root (python.exe next to sse-gui.exe),
rem matching installer resources map "pyembed/python -> ./"; main.rs Standalone finds python.exe in exe dir
xcopy /e /q /y /i src-tauri\pyembed\python "%STAGE%" >nul
if errorlevel 1 echo [build-gui] portable stage copy failed
if errorlevel 1 exit /b 1
powershell -NoProfile -Command "Compress-Archive -Path '%STAGE%\*' -DestinationPath '%PORTABLE_ZIP%' -Force"
if errorlevel 1 echo [build-gui] portable.zip failed
if errorlevel 1 exit /b 1
rd /s /q "%STAGE%"

echo.
echo [build-gui] done, outputs in build\bundle-release\ :
if exist build\bundle-release\sse-gui.exe echo   sse-gui.exe
for %%F in (build\bundle-release\bundle\msi\*.msi) do echo   %%~nxF
for %%F in (build\bundle-release\bundle\nsis\*.exe) do echo   %%~nxF
for %%F in (build\bundle-release\*portable*.zip) do echo   %%~nxF
endlocal
exit /b 0

:fe_fail
popd
echo [build-gui] frontend build failed
endlocal
exit /b 1
