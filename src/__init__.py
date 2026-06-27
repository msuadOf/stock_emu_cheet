"""src 包：stock 存档编辑器的多前端架构。

分层（依赖严格单向，禁止环依赖）::

    cli  ──▶  core  ◀──  tui
                   ◀──  gui/backend  ◀── gui/frontend

- ``src/core``：纯业务后端，只依赖标准库，**绝不** import tui/cli/gui。
  其中 ``src/core/extra`` 放社区贡献的 extra 功能（公告/退市/增发/分红等）。
- ``src/tui``：交互式文本界面（测试加载 ``src/tui/frontend/app.py`` 作为 ``sse`` 模块；
  ``backend`` 放纯无 I/O 辅助，``frontend`` 放交互壳）。
- ``src/cli``：非交互式命令行（子命令式），只 import ``src.core``。
- ``src/gui``：pytauri 桌面端（backend 命令层 + React 前端 + 启动器）。
"""
