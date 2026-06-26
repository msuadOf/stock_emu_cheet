#!/usr/bin/env bash
# 一键预览 CLI（非交互式子命令前端）
# 用法: scripts/run-cli.sh <子命令> [参数...]
#   scripts/run-cli.sh --help                      # 查看所有子命令
#   scripts/run-cli.sh list-saves -d "D:/saves"    # 列存档
#   scripts/run-cli.sh set-pe 2001 5.0 --save x.sav --yes
set -euo pipefail
cd "$(dirname "$0")/.."   # 切到项目根

export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"

echo "▶ 启动 CLI ..."
python -m src.cli.cli "$@"
