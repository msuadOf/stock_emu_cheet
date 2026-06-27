"""存档数据访问：纯 Editor（落盘）+ 数据助手。

``Editor`` 是**纯**落盘/进程层：``load()`` 读 .sav 构造 ``SaveModel``，
``save(model, force)`` 序列化内部树写盘 + 备份 + 进程守卫。**无 print/confirm**——
``force`` 由调用方决定（TUI 交互壳做 confirm，CLI 用 --force，GUI 用对话框结果）。

交互式 ``Editor``（带 confirm/警告打印）留 ``src/tui/frontend/app.py`` 作 ``sse`` 兼容测试。
本模块同时保留 ``load_json``/``write_json_compact`` 等无副作用助手（CLI/GUI 复用）。
"""
import json
import shutil
from datetime import datetime
from pathlib import Path

from .savemodel import SaveModel


def load_json(path):
    """从路径读取存档 JSON（utf-8），返回 dict。"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def backup(path, bak=None):
    """为存档做带时间戳的 .sav.bak.* 备份；返回备份路径。"""
    path = Path(path)
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


class Editor:
    """纯落盘/进程层：读 .sav → SaveModel，SaveModel → 写 .sav。

    与 TUI 的交互版 ``Editor``（带 confirm/警告）不同，本类**不打印、不确认**。
    ``save(force=...)`` 的 force 由调用方决定；游戏运行守卫通过 ``is_game_running``
    参数注入（避免 core 依赖 subprocess 副作用，也便于测试）。
    """

    def __init__(self, path):
        self.path = Path(path)
        self.model: SaveModel | None = None
        self.modified = False

    def load(self):
        """读 .sav → SaveModel（存内部值，与文件一一对应）。"""
        self.model = SaveModel.load(self.path)
        self.modified = False
        return self.model

    def save(self, model=None, force=False, is_game_running=None):
        """把 model 写回 .sav。

        - model: 默认用 self.load() 加载的 model。
        - is_game_running: 可选的可调用对象，返回 bool。若返回 True 且 force=False，
          则不写盘、返回 False（调用方应据此提示用户）。
        - 返回 True=已写盘；False=未写盘（游戏运行且未 force）。
        无 print/confirm——纯逻辑。
        """
        if model is None:
            model = self.model
        if model is None:
            return False
        if is_game_running is not None and is_game_running() and not force:
            return False
        # 备份 + 写盘
        bak = self.path.with_suffix(".sav.bak." + datetime.now().strftime("%Y%m%d_%H%M%S"))
        if self.path.exists():
            shutil.copy2(self.path, bak)
        model.write(self.path)
        self.modified = False
        return True

