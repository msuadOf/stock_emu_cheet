#!/usr/bin/env bash
# 一键预览 GUI（开发模式：Vite HMR + tauri dev，热更新）
#
# 前提（首次）:
#   pip install uv            # 已有可跳过
#   uv venv && uv pip install -e ".[gui]" -e src-tauri   # 建 venv + 装 pytauri + 项目
#   cd src/gui/frontend && npm install && cd ../..       # 装前端依赖
#   还需 Rust(MSVC) + tauri-cli（见 README）
#
# 用法: scripts/run-gui.sh
# 工作机制:
#   1) 起 Vite dev server (后台, :5173, HMR)
#   2) 激活 venv，设 DEV_SERVER，跑 cargo tauri dev（加载 dev server）
set -euo pipefail
cd "$(dirname "$0")/.."   # 项目根

VENV_DIR="$PWD/.venv"
FRONTEND="$PWD/src/gui/frontend"

# ---- 检查前提 ----
command -v cargo >/dev/null  || { echo "✗ 未找到 cargo，请先装 Rust(MSVC)。"; exit 1; }
[ -d "$VENV_DIR" ]           || { echo "✗ 未找到 .venv，先运行: uv venv && uv pip install -e \".[gui]\" -e src-tauri"; exit 1; }
[ -d "$FRONTEND/node_modules" ] || { echo "✗ 前端依赖未装，先运行: cd src/gui/frontend && npm install"; exit 1; }

# ---- 激活 venv ----
# shellcheck disable=SC1091
source "$VENV_DIR/Scripts/activate" 2>/dev/null || source "$VENV_DIR/bin/activate"
export VIRTUAL_ENV="$VENV_DIR"   # main.rs 用它定位 venv 解释器

# ---- 起 Vite dev server (后台) ----
echo "▶ 启动 Vite dev server (:5173, HMR) ..."
( cd "$FRONTEND" && npm run dev ) &
VITE_PID=$!
trap 'kill $VITE_PID 2>/dev/null || true' EXIT INT TERM

# 等 Vite 起来
sleep 3

# ---- tauri dev ----
echo "▶ 启动 tauri dev（加载 dev server）..."
export DEV_SERVER="http://localhost:5173"
cd src-tauri
cargo tauri dev
