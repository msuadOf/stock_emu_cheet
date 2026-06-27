"""``src.tui.backend``：TUI 的纯辅助层（**无 I/O、无 input/print/confirm**）。

只放纯字符串组装 / 纯查询（如展示明细、菜单标题文本），便于复用与测试。
绝不 import ``frontend``，绝不产生交互副作用（那是 frontend 的职责）。
只依赖标准库与 ``src.core``。
"""
