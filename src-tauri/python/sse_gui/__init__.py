"""sse_gui：pytauri standalone 模式的 Python 入口包。

Rust crate（src-tauri/）通过 `PythonScript::Module("sse_gui")` 运行本包的
`__main__.py`，并把 `ext_mod`（Rust 编译的 PyO3 扩展）注入到本进程，
使本包能从 `pytauri` 拿到 `builder_factory` / `context_factory`。

命令注册复用 `src/gui/backend/commands.py`（同一个业务后端，零重复）。
"""
import sys
from pathlib import Path

# 让本进程能 import 项目根的 src 包（core / gui.backend），无论从哪启动
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from anyio.from_thread import start_blocking_portal  # noqa: E402
from pytauri import builder_factory, context_factory  # noqa: E402

# 复用现有业务后端命令（src/gui/backend/commands.py）
from src.gui.backend.commands import commands  # noqa: E402


def main() -> int:
    """启动 Tauri 应用：构造 app、注册命令、运行。

    ``commands.generate_handler(portal)`` 需要一个存活的 ``BlockingPortal``，
    且 portal 必须在 app 运行期间保持有效，所以用 ``with`` 包住 ``run_return()``。
    """
    with start_blocking_portal("asyncio") as portal:
        app = builder_factory().build(
            context=context_factory(),
            invoke_handler=commands.generate_handler(portal),
        )
        return app.run_return()
