"""``src.tui.frontend``：TUI 的交互层（= 测试加载的 ``sse`` 模块）。

``src/tui/frontend/app.py`` 被 ``tests/helpers.py`` 用 ``importlib`` 加载为名为
``sse`` 的模块，所有调 ``input/print/clear/pause/confirm/is_game_running`` 的函数
都集中在此单一模块，保证 ``mock.patch("sse.input" / "sse.print" / ...)`` 仍命中。

业务逻辑全部转调 ``src.core`` 的纯函数（收 SaveModel），本模块只做「收输入 + 打印 +
confirm」的瘦交互壳；纯字符串组装放 ``src/tui/backend``。
"""
