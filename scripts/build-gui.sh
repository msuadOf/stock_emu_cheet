#!/usr/bin/env bash
# 一键编译打包 GUI（standalone pytauri，产物 .msi/.exe 放到 build/）
#
# 产物（项目根 build/ 下）:
#   build/bundle-release/sse-gui.exe
#   build/bundle-release/bundle/msi/*.msi
#   build/bundle-release/bundle/nsis/*-setup.exe
#
# 前提: Rust(MSVC) + tauri-cli + uv + Node。首次会自动下载 python-build-standalone。
set -euo pipefail
cd "$(dirname "$0")/.."   # 项目根

# 杀掉残留的 sse-gui 进程，否则它占着 pyembed 的 DLL 会导致 rebuild 报 os error 32
taskkill //IM sse-gui.exe //F >/dev/null 2>&1 || true

PYEXE="$PWD/src-tauri/pyembed/python/python.exe"

# ---- 自动把 rustup/uv 的安装目录加进 PATH（常见安装位置）----
for d in "$HOME/.cargo/bin" "$HOME/.local/bin"; do
  [ -d "$d" ] && case ":$PATH:" in *":$d:"*) ;; *) export PATH="$d:$PATH" ;; esac
done

# ---- 检查工具链 ----
command -v cargo >/dev/null || { echo "✗ 未找到 cargo，请先装 Rust(MSVC) 并重启终端。"; exit 1; }
command -v uv >/dev/null    || { echo "✗ 未找到 uv，请先装 uv (https://docs.astral.sh/uv/)。"; exit 1; }
command -v npm >/dev/null   || { echo "✗ 未找到 npm/Node，请先装 Node。"; exit 1; }

# ---- 1) 前端构建 ----
echo "▶ [1/4] 构建前端 (Vite -> dist-frontend) ..."
( cd src/gui/frontend && npm install --no-audit --no-fund && npm run build )

# ---- 2) 准备嵌入 Python（python-build-standalone）----
echo "▶ [2/4] 准备嵌入 Python ..."
# 固定的嵌入 Python 版本（python-build-standalone release tag + 文件名）
PY_TAG="20260623"
PY_FILE="cpython-3.13.14+${PY_TAG}-x86_64-pc-windows-msvc-install_only_stripped.tar.gz"
if [ ! -x "$PYEXE" ]; then
  echo "  下载 python-build-standalone 3.13 (msvc, stripped) ..."
  mkdir -p src-tauri/pyembed
  curl -fL --retry 3 -o src-tauri/pyembed/py.tar.gz \
    "https://github.com/astral-sh/python-build-standalone/releases/download/${PY_TAG}/${PY_FILE}"
  ( cd src-tauri/pyembed && tar xzf py.tar.gz && rm -f py.tar.gz )
fi
echo "  嵌入 Python: $("$PYEXE" --version 2>&1)"

# ---- 3) 把项目 + sse_gui 入口包装进嵌入 Python（非 editable，否则打包后路径失效）----
echo "▶ [3/4] 安装项目到嵌入 Python ..."
export PYTAURI_STANDALONE=1
# 项目根（stock-save-editor，含 src.*）
uv pip install --python "$PYEXE" --reinstall-package stock-save-editor .
# src-tauri/ 目录（其 pyproject 声明 sse-gui 入口包）
uv pip install --python "$PYEXE" --reinstall-package sse-gui ./src-tauri

# ---- 4) tauri build ----
echo "▶ [4/4] tauri build (release, 产物 -> build/) ..."
export PYO3_PYTHON="$PYEXE"
cd src-tauri
cargo tauri build --config tauri.bundle.json -- --profile bundle-release

cd ../..
echo ""
echo "✅ 打包完成，产物在 build/bundle-release/ :"
ls -la build/bundle-release/sse-gui.exe \
       build/bundle-release/bundle/msi/*.msi \
       build/bundle-release/bundle/nsis/*.exe 2>/dev/null
