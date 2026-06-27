#!/usr/bin/env bash
# 直接跑测试（免打包/编译）。与打包共用同一份代码，强一致性。
#
# 用法:
#   scripts/test.sh             # 全量
#   scripts/test.sh -v          # 详细
#   scripts/test.sh tests.test_core_ops   # 单模块
set -euo pipefail
cd "$(dirname "$0")/.."   # 项目根

export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
python run_tests.py "$@"
