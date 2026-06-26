"""存档数据访问的纯函数。

注意：交互式的 ``Editor`` 类（其 ``save()`` 会 confirm / 检测游戏进程 / 打印）
留在 ``src/tui/app.py``（=测试加载的 ``sse`` 模块），因为 ``save()`` 内部裸调
``is_game_running()`` / ``confirm()``，必须解析到测试 patch 的 ``sse.*``。

本模块只提供无副作用的、可被 CLI/GUI 复用的纯数据访问与磁盘写入助手。
"""
import json
import shutil
from datetime import datetime


def load_json(path):
    """从路径读取存档 JSON（utf-8），返回 dict。"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def backup(path, bak=None):
    """为存档做带时间戳的 .sav.bak.* 备份；返回备份路径。"""
    path = __import__("pathlib").Path(path)
    if bak is None:
        bak = path.with_suffix(".sav.bak." + datetime.now().strftime("%Y%m%d_%H%M%S"))
    if path.exists():
        shutil.copy2(path, bak)
    return bak


def write_json_compact(path, data):
    """把存档以紧凑 JSON 写回磁盘（ensure_ascii=False，无空白）。"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def stocks_of(data):
    """从存档 dict 取股票列表。"""
    return data.get("Market", {}).get("Stocks", [])


def find_stock(data, code):
    """按 Code 在存档里查找某只股票 dict；找不到返回 None。"""
    for s in stocks_of(data):
        if s.get("Info", {}).get("Code") == code:
            return s
    return None


def codes_of(data):
    """返回存档内所有股票代码（已排序）。"""
    return sorted([s.get("Info", {}).get("Code") for s in stocks_of(data)
                   if s.get("Info", {}).get("Code") is not None])
