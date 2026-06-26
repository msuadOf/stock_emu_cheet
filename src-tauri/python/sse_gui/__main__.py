"""sse_gui 入口：`python -m sse_gui`（Rust standalone 等价于此）。"""
import sys
from multiprocessing import freeze_support

from sse_gui import main

# pyinstaller/multiprocessing 冻结支持；standalone 打包后避免 spawn 循环
freeze_support()
sys.exit(main())
