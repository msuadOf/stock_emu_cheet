"""存档瘦身/清理的纯核心：清空公告、清空交易历史、裁剪 HuddleNpc 持仓。

这些是原版主菜单的「Cleanup 清理」三件套（功能 5/6/7），原本内联在 TUI；
抽成收 ``SaveModel`` 的纯函数，供 CLI / GUI 共享。无 I/O、无交互（confirm 由调用方决定）。
"""


def clear_notice_group(save):
    """清空 Market.NoticeGroup（兼容 list / dict 两形态：list→[]，dict→每键[]）。

    save: SaveModel。返回 {before: 清空前总条数, form: 'list'|'dict'}。
    幂等：已空时 before=0。
    """
    market = save._d.setdefault("Market", {})
    ng = market.get("NoticeGroup")
    if isinstance(ng, list):
        before = len(ng)
        market["NoticeGroup"] = []
        return {"before": before, "form": "list"}
    if isinstance(ng, dict):
        before = sum(len(v) if isinstance(v, list) else 0 for v in ng.values())
        for k in ng:
            ng[k] = []
        return {"before": before, "form": "dict"}
    # NoticeGroup 不存在或为其他类型 → 置空 dict
    before = 0
    market["NoticeGroup"] = {}
    return {"before": before, "form": "empty"}


def clear_trade_type(save):
    """清空 Player.TradeType（交易历史）。返回 {before: 清空前条数}。"""
    player = save._d.setdefault("Player", {})
    tt = player.get("TradeType", []) or []
    before = len(tt)
    player["TradeType"] = []
    return {"before": before}


def trim_huddle_npc(save, keep):
    """裁剪每个 HuddleNpc 账户的 StockPos，保留前 keep 条。

    save: SaveModel。keep: 每个账户保留条数（0=全部清空）。返回 {before, after, accounts}。
    """
    market = save._d.setdefault("Market", {})
    hn = market.get("HuddleNpc", []) or []
    before = 0
    after = 0
    for h in hn:
        sp = h.get("StockPos", []) or []
        before += len(sp)
        if len(sp) > keep:
            h["StockPos"] = sp[:keep]
        after += len(h.get("StockPos", []))
    market["HuddleNpc"] = hn
    return {"before": before, "after": after, "accounts": len(hn)}
