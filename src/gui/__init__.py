"""GUI 包：pytauri 桌面端。

- ``app.py``：pytauri 启动器（只起窗口、路由 IPC 到 backend，不含业务逻辑）。
- ``backend/``：GUI 专属后端（pytauri ``@commands.command()`` 命令层，依赖 ``src.core``）。
- ``frontend/``：React + Vite + TS 前端（通过 ``pyInvoke`` 调 backend）。
"""
