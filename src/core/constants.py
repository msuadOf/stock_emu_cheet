"""全局常量。纯数据，无副作用，无依赖。"""
from pathlib import Path

# 默认存档目录（游戏存档路径）
DEFAULT_SAVE_DIR = Path.home() / "AppData" / "LocalLow" / "LoneCat" / "StocksMainForceSimulator" / "Saves"
# 游戏进程名（用于进程防覆盖检测）
GAME_PROCESS_NAME = "StocksMainForceSimulator.exe"

# 板块代码 -> 名称
SECTOR_MAP = {
    10: "金融", 20: "科技", 30: "工业", 40: "能源",
    50: "消费", 60: "医药", 70: "交通", 80: "房产",
    90: "环保", 100: "农业"
}

# 交易所代码 -> 名称
BOURSE_MAP = {
    1: "上海证券交易所",
    2: "深圳证券交易所"
}
