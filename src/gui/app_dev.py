"""GUI 开发模式入口（pytauri-wheel，**免 Rust 编译**）。

与打包用的 standalone 入口 ``src/gui/app.py``（Rust crate 主导）不同，本入口是
**纯 Python**：``pip install pytauri-wheel``（预构建 wheel，无需 Rust 工具链）后
直接 ``python -m src.gui.app_dev`` 即可起 GUI 窗口。

**与打包共用同一份代码**（强一致性）：
- backend 命令：``src/gui/backend/commands.py``（同一份 @commands.command()）
- 业务后端：``src/core``（同一份）
- 前端：``src/gui/frontend``（vite dev server，HMR）

开发流程：
  1) ``cd src/gui/frontend && npm install && npm run dev``  (vite :5173, HMR)
  2) ``pip install pytauri-wheel``  (一次性，免 Rust)
  3) ``DEV_SERVER=http://localhost:5173 python -m src.gui.app_dev``
前端改动秒级生效（HMR），改 Python 重跑即可，**全程不碰 Rust 编译**。

打包时改用 ``scripts/build-gui.sh``（standalone，出 .msi/.exe），用的是同一份
backend + core + 前端构建产物。
"""
import os
import sys
from pathlib import Path

from anyio.from_thread import start_blocking_portal
from pytauri_wheel.lib import builder_factory, context_factory

# 复用与 standalone 相同的命令注册（同一份 backend）
from src.gui.backend.commands import commands

# wheel 模式下「src-tauri 目录」概念不存在；context_factory 用本文件所在目录
# 作为 capabilities/Tauri 配置的查找根。dev 模式用 DEV_SERVER 提供前端。
SRC_TAURI_DIR = Path(__file__).parent.absolute()
DEV_SERVER = os.environ.get("DEV_SERVER")


def main() -> int:
    tauri_config = None
    if DEV_SERVER is not None:
        tauri_config = {"build": {"frontendDist": DEV_SERVER}}

    with start_blocking_portal("asyncio") as portal:
        app = builder_factory().build(
            context=context_factory(SRC_TAURI_DIR, tauri_config=tauri_config),
            invoke_handler=commands.generate_handler(portal),
        )
        return app.run_return()


if __name__ == "__main__":
    sys.exit(main())
