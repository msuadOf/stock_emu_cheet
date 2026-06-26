"""pytauri 启动器：起 WebView2 主窗，把 IPC 路由到 ``src/gui/backend/commands``。

不含业务逻辑——只负责构造 app、注册 backend 的命令 handler、运行。
开发模式可用环境变量 ``DEV_SERVER=http://localhost:5173`` 指向 Vite dev server（HMR）；
生产模式用 ``npm run build`` 产出的 ``src/gui/dist-frontend``（见 Tauri.toml 的 frontendDist）。
"""
import os
import sys
from pathlib import Path

from anyio.from_thread import start_blocking_portal
from pytauri_wheel.lib import builder_factory, context_factory

from src.gui.backend.commands import commands

# 本模块所在目录即「src-tauri」目录（含 Tauri.toml / capabilities/ / frontend/）
SRC_TAURI_DIR = Path(__file__).parent.absolute()

# 开发模式：是否用前端 dev server（如 Vite 的 http://localhost:5173）提供前端资源
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
