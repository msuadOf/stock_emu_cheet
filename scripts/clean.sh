#!/usr/bin/env bash
# 清理构建产物与依赖（不影响源码与 git 跟踪文件）
#
# 用法:
#   scripts/clean.sh           # 清标准产物
#   scripts/clean.sh --deep    # 连 node_modules / .venv / pyembed 一起清（重新拉依赖）
set -euo pipefail
cd "$(dirname "$0")/.."   # 项目根

DEEP=0
[ "${1:-}" = "--deep" ] && DEEP=1

removed=0
rmrf() {
  for p in "$@"; do
    if [ -e "$p" ]; then
      echo "  删除 $p"
      rm -rf "$p"
      removed=1
    fi
  done
}

echo "▶ 清理构建产物 ..."

# Rust/Tauri 构建输出（含最终 .msi/.exe）
rmrf build src-tauri/target

# 前端构建产物 + TS 增量缓存
rmrf src/gui/dist-frontend src/gui/frontend/tsconfig.tsbuildinfo

# tauri 生成的中间文件
rmrf src-tauri/gen src-tauri/WixTools src-tauri/NSIS src-tauri/nsis

# Python 字节码缓存
find . -type d -name __pycache__ -not -path "*/node_modules/*" -prune -exec rm -rf {} + 2>/dev/null || true

if [ "$DEEP" -eq 1 ]; then
  echo "▶ --deep：连依赖一起清 ..."
  rmrf src/gui/frontend/node_modules
  rmrf .venv
  rmrf src-tauri/pyembed    # 嵌入的 python-build-standalone（下次 build-gui.sh 会重下）
fi

[ "$removed" -eq 0 ] && echo "  (无构建产物可清，工作区已干净)"
echo "✅ 清理完成"
