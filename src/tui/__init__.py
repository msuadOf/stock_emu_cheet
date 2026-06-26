"""TUI 包：交互式文本界面。

测试基础设施（``tests/helpers.py``）通过 ``importlib`` 把
``src/tui/app.py`` 加载为名为 ``sse`` 的模块，所有交互函数都集中在此单一模块，
保证 ``mock.patch("sse.input" / "sse.print" / ...)`` 仍然生效（见约束 2）。
"""
