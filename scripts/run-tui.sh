#!/usr/bin/env bash
# 一键预览 TUI（交互式终端前端）
# 用法: scripts/run-tui.sh [存档目录]
#   scripts/run-tui.sh                     # 用默认存档目录
#   scripts/run-tui.sh "D:/my/saves"       # 指定存档目录
set -euo pipefail
cd "$(dirname "$0")/.."   # 切到项目根

# 确保 src 包可 import（项目根在 PYTHONPATH）
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"

echo "▶ 启动 TUI ..."
if [ $# -ge 1 ]; then
  python -m src.tui.frontend.app -d "$1"
else
  python -m src.tui.frontend.app
fi
