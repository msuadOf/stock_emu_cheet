"""``src.core``：三前端共享的纯业务后端（只依赖标准库）。

禁止 import ``src.tui`` / ``src.cli`` / ``src.gui``（含 ``gui/backend``），
否则构成环依赖（见架构约束 0）。

交互式的 ``Editor`` 类（含 confirm/进程检测的 ``save()``）留在 ``src/tui/app.py``，
这里只导出可复用的纯函数与常量。
"""
from .constants import (
    DEFAULT_SAVE_DIR,
    GAME_PROCESS_NAME,
    SECTOR_MAP,
    BOURSE_MAP,
)
from .calcs import (
    fmt_p, fmt_v, fmt_m, fmt_shares,
    calc_pe, calc_pb, calc_market_cap,
)
from .saves import (
    is_game_running,
    find_save_dirs,
    list_saves,
    default_save_dir,
    list_save_slots,
    list_save_files,
)
from . import editor
from .editor import (
    Editor,
    load_json, backup, write_json_compact,
    stocks_of, find_stock, codes_of,
)
from . import savemodel
from .savemodel import (
    SaveModel, StockModel, InfoModel, CandleModel,
    AccountModel, PositionModel, PlayerModel, NPC_KEYS,
)
from . import stock_ops
from .stock_ops import (
    set_target_pe, set_target_pb, set_target_debt_ratio,
    set_price_init, set_price_fact_sync_candles, set_rate_limit,
    parse_magnitude, apply_financial_fields,
    clear_npc_quotes, set_npc_quotes_by_median, set_npc_quotes_custom,
    apply_notice_style,
    dilute_for_shortage, dilute_stock_for_shortage,
    batch_set_npc_quotes, batch_set_notice_style,
)
from . import player_ops
from .player_ops import (
    add_player_position, modify_player_position, delete_player_position,
    set_player_amount, sync_npc_holdings,
    batch_set_player_pct,
)
# extra（社区贡献 extra 功能）作为子包导出
from . import extra

__all__ = [
    # constants
    "DEFAULT_SAVE_DIR", "GAME_PROCESS_NAME", "SECTOR_MAP", "BOURSE_MAP",
    # calcs
    "fmt_p", "fmt_v", "fmt_m", "fmt_shares",
    "calc_pe", "calc_pb", "calc_market_cap",
    # saves
    "is_game_running", "find_save_dirs", "list_saves",
    "default_save_dir", "list_save_slots", "list_save_files",
    # editor helpers
    "editor", "load_json", "backup", "write_json_compact",
    "stocks_of", "find_stock", "codes_of",
    # stock ops (主干编辑纯核心)
    "stock_ops",
    "set_target_pe", "set_target_pb", "set_target_debt_ratio",
    "set_price_init", "set_price_fact_sync_candles", "set_rate_limit",
    "parse_magnitude", "apply_financial_fields",
    "clear_npc_quotes", "set_npc_quotes_by_median", "set_npc_quotes_custom",
    "apply_notice_style",
    "dilute_for_shortage", "dilute_stock_for_shortage",
    "batch_set_npc_quotes", "batch_set_notice_style",
    # player ops
    "player_ops",
    "add_player_position", "modify_player_position", "delete_player_position",
    "set_player_amount", "sync_npc_holdings",
    "batch_set_player_pct",
]
