"""``src.core.extra``：社区贡献的 extra 功能（公告/退市/增发/分红/市场整顿等）的纯核心。

这些功能在原代码中标注为 ``# [extra]``（原写 ``# [v2 extra]``，已统一去掉错误的「v2」），
物理隔离到此子包，便于与原主干功能区分。本包只依赖标准库与 ``src.core`` 同包，
绝不 import tui/cli/gui。
"""
from .notice_ops import (
    get_current_game_day,
    get_or_create_delisted_pool,
    build_stock_notice,
    append_notice_normal,
    filter_delisted_candidates,
    build_performance_report,
    commit_performance_report,
)
from .market_ops import (
    NPC_KEYS,
    collect_npc_holdings,
    clear_npc_stock_positions,
    move_npc_to_retail,
    rectify_market,
)
from .corporate_ops import (
    collect_dividend_vols,
    cash_dividend_limits,
    apply_cash_dividend,
    apply_stock_dividend,
    compute_placement,
    apply_private_placement,
    remove_stock_from_market,
    remove_code_notices,
    remove_player_position,
    delist_to_b,
    delist_to_a,
    build_new_stock_restore,
    build_new_stock_custom,
    attach_stock_to_market,
)

__all__ = [
    # notice_ops
    "get_current_game_day", "get_or_create_delisted_pool",
    "build_stock_notice", "append_notice_normal", "filter_delisted_candidates",
    "build_performance_report", "commit_performance_report",
    # market_ops
    "NPC_KEYS", "collect_npc_holdings", "clear_npc_stock_positions",
    "move_npc_to_retail", "rectify_market",
    # corporate_ops
    "collect_dividend_vols", "cash_dividend_limits", "apply_cash_dividend", "apply_stock_dividend",
    "compute_placement", "apply_private_placement",
    "remove_stock_from_market", "remove_code_notices", "remove_player_position",
    "delist_to_b", "delist_to_a",
    "build_new_stock_restore", "build_new_stock_custom", "attach_stock_to_market",
]
