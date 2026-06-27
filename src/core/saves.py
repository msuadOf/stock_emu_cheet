"""存档目录扫描 + 游戏进程检测。纯 I/O 辅助（无交互）。

注意：``is_game_running`` 通过 ``subprocess.run`` 调用系统 tasklist。
TUI 层（``src/tui/frontend/app.py``）为兼容测试的 ``mock.patch("sse.subprocess.run")``，
会在本地重新定义一个薄 ``is_game_running`` 包装；本模块是真正的实现来源。
"""
import subprocess
from datetime import datetime
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


def default_save_dir():
    """返回默认存档根目录（游戏存档路径）。三端统一用它作起点。"""
    return Path(DEFAULT_SAVE_DIR)


def find_save_dirs(base_dir=DEFAULT_SAVE_DIR):
    """枚举 base_dir 下含 .sav 文件的子目录（即游戏存档槽）。"""
    base_dir = Path(base_dir)
    if not base_dir.exists():
        return []
    return [p for p in base_dir.iterdir() if p.is_dir() and any(p.glob("*.sav"))]


def list_saves(d):
    """列出某存档目录下所有 .sav 文件（按名排序）。"""
    return sorted([p for p in d.iterdir() if p.suffix == ".sav" and p.is_file()])


# ------------------------------------------------------------------
# 供选择的高层 API：返回结构化、前端友好的描述（dict），三端共用。
# 流程：default_save_dir() -> list_save_slots() 选槽 -> list_save_files() 选文件
# ------------------------------------------------------------------
def list_save_slots(base_dir=DEFAULT_SAVE_DIR):
    """列出 base_dir 下可选的存档槽（含 .sav 的子目录）。

    返回 [{name, path, file_count}, ...]，按目录名排序。
    """
    out = []
    for p in find_save_dirs(base_dir):
        out.append({
            "name": p.name,
            "path": str(p),
            "file_count": len(list(p.glob("*.sav"))),
        })
    out.sort(key=lambda x: x["name"])
    return out


def _file_info(p):
    """把一个 .sav 路径转成前端友好的描述 dict。"""
    st = p.stat()
    return {
        "name": p.name,
        "path": str(p),
        "size_kb": round(st.st_size / 1024, 1),
        "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
    }


def list_save_files(directory):
    """列出某存档目录下所有 .sav 文件（按名排序）。

    返回 [{name, path, size_kb, modified}, ...]。
    directory 不存在或为空时返回 []。
    """
    d = Path(directory)
    if not d.exists() or not d.is_dir():
        return []
    return [_file_info(p) for p in list_saves(d)]

