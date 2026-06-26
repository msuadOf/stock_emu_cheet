"""GUI 专属后端：pytauri ``@commands.command()`` 命令层。

依赖 ``src.core``（单向：backend → core；core 不知道 backend 存在）。
每个命令把 core 纯函数包装成可被前端 ``pyInvoke`` 调用的接口。
extra 命令标注 ``# [extra]``。
"""
