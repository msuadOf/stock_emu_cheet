#!/usr/bin/env bash
# 一键开发预览（**免编译/打包**，秒起）。与打包共用同一份 src/core + backend。
#
# 用法:
#   scripts/dev.sh tui [存档目录]        # 终端前端
#   scripts/dev.sh cli <子命令> [参数]   # 命令行前端（如 --help / list-saves）
#   scripts/dev.sh gui                   # 桌面前端（pytauri-wheel 模式，免 Rust！）
#
# 一致性：dev 与打包(build-gui.sh)共用 src/core + src/gui/backend/commands.py + 前端，
# 改一处代码两端都生效。GUI dev 用 pytauri-wheel（预构建，无需 Rust 工具链）。
set -euo pipefail
cd "$(dirname "$0")/.."   # 项目根

MODE="${1:-}"
[ -z "$MODE" ] && { echo "用法: scripts/dev.sh {tui|cli|gui} [参数]"; exit 1; }
shift || true

export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"

case "$MODE" in
  tui)
    echo "▶ TUI 开发模式 ..."
    if [ $# -ge 1 ]; then python -m src.tui.app -d "$1"; else python -m src.tui.app; fi
    ;;
  cli)
    echo "▶ CLI 开发模式 ..."
    python -m src.cli.cli "$@"
    ;;
  gui)
    # GUI wheel 模式：免 Rust，pip install pytauri-wheel 即可。前端用 vite dev (HMR)。
    VENV="$PWD/.venv"
    FRONTEND="$PWD/src/gui/frontend"
    command -v uv >/dev/null || { echo "✗ 需要 uv (pip install uv)"; exit 1; }
    # 首次自动建 venv + 装 pytauri-wheel + 项目
    if [ ! -d "$VENV" ]; then
      echo "  首次：建 dev venv + 装 pytauri-wheel ..."
      uv venv --python-preference only-system
      uv pip install --python "$VENV/Scripts/python.exe" "pytauri-wheel==0.8.*" -e .
    fi
    [ -d "$FRONTEND/node_modules" ] || { echo "  首次：装前端依赖 ..."; ( cd "$FRONTEND" && npm install --no-audit --no-fund ); }
    # 起 vite dev server (后台, HMR)
    echo "▶ 起 Vite dev server (:5173, HMR) ..."
    ( cd "$FRONTEND" && npm run dev ) &
    VITE_PID=$!
    trap 'kill $VITE_PID 2>/dev/null || true' EXIT INT TERM
    sleep 4
    # wheel 模式跑 GUI（免 Rust）
    echo "▶ 起 GUI (pytauri-wheel, 免 Rust 编译) ..."
    DEV_SERVER=http://localhost:5173 "$VENV/Scripts/python.exe" -m src.gui.app_dev
    ;;
  *)
    echo "✗ 未知模式: $MODE（可选 tui|cli|gui）"; exit 1
    ;;
esac
