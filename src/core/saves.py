"""存档目录扫描 + 游戏进程检测。纯 I/O 辅助（无交互）。

注意：``is_game_running`` 通过 ``subprocess.run`` 调用系统 tasklist。
TUI 层（``src/tui/app.py``）为兼容测试的 ``mock.patch("sse.subprocess.run")``，
会在本地重新定义一个薄 ``is_game_running`` 包装；本模块是真正的实现来源。
"""
import subprocess
from pathlib import Path

from .constants import DEFAULT_SAVE_DIR, GAME_PROCESS_NAME


def is_game_running():
    """检测游戏进程是否在运行（Windows tasklist）。

    用 ``CREATE_NO_WINDOW`` 风格已被移除（旧版会导致崩溃），这里直接捕获输出。
    任何异常都视为「未运行」返回 False。
    """
    try:
        result = subprocess.run(
            f'tasklist /FI "IMAGENAME eq {GAME_PROCESS_NAME}"',
            capture_output=True, text=True, shell=True,
        )
        return GAME_PROCESS_NAME.lower() in result.stdout.lower()
    except Exception:
        return False


def find_save_dirs(base_dir=DEFAULT_SAVE_DIR):
    """枚举 base_dir 下含 .sav 文件的子目录（即游戏存档槽）。"""
    base_dir = Path(base_dir)
    if not base_dir.exists():
        return []
    return [p for p in base_dir.iterdir() if p.is_dir() and any(p.glob("*.sav"))]


def list_saves(d):
    """列出某存档目录下所有 .sav 文件（按名排序）。"""
    return sorted([p for p in d.iterdir() if p.suffix == ".sav" and p.is_file()])
