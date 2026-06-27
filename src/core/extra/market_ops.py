"""[extra] 市场整顿 / 机构转散户 相关纯核心（社区贡献 extra 功能）。

从原 TUI 的 ``change_npc_all_to_retail`` 与 ``market_rectification`` 中剥离
「遍历账户 + 改持仓」的纯部分；交互（明细打印/confirm）仍留 TUI。

**已迁移到 SaveModel**：函数收 ``SaveModel``（原收 Editor ``e``）。
筹码守恒全程在**内部值**上做精确整数运算（``*_raw`` getter / 直接写内部 dict），
因为守恒要求精确取整——切到显示值会引入 /100 浮点漂移。

标记统一为 ``# [extra]``。返回结构化的摘要 dict，供 TUI/GUI 打印。
"""

# [extra] extra 功能（社区贡献），非原主干。

# 5 类 NPC 账户键名
NPC_KEYS = ["AloneNpc", "HuddleNpc", "MessageNpc", "RelayNpc", "SneakNpc"]


def _npc_positions(save, code):
    """汇总某股票在所有 NPC 账户下的 VolumeUsable(内部值) 总和。save: SaveModel。"""
    total = 0
    for k in NPC_KEYS:
        for acc in save.npc_account_list(k):
            for p in acc.get("StockPos", []) or []:
                if p.get("Code") == code:
                    total += int(p.get("VolumeUsable", 0))
    return total


# [extra]
def collect_npc_holdings(save):
    """扫描所有 NPC 账户，汇总每只股票被持有的总量(内部值)。

    save: SaveModel。返回 {code: total_volume}（仅含被持有的股票）。
    """
    holdings = {}
    for stock in save.stocks:
        code = stock.info.code
        total = 0
        for k in NPC_KEYS:
            for acc in save.npc_account_list(k):
                sp = acc.get("StockPos", []) or []
                for p in sp:
                    if p.get("Code") == code:
                        total += int(p.get("VolumeUsable", 0))
        if total > 0:
            holdings[code] = total
    return holdings


# [extra]
def clear_npc_stock_positions(save, code):
    """从所有 NPC 账户删除某股票的持仓。save: SaveModel。"""
    market = save._d.get("Market", {})
    for k in NPC_KEYS:
        for acc in market.get(k, []) or []:
            sp = acc.get("StockPos", []) or []
            acc["StockPos"] = [p for p in sp if p.get("Code") != code]


# [extra]
def move_npc_to_retail(save, holdings=None):
    """把指定(或全部) NPC 持仓转入对应股票的散户 VolumeUsableSell，并做筹码守恒平账。

    save: SaveModel。holdings: {code: volume(内部值)}；None 时先扫描全市场。
    返回 {code: transferred} 摘要。
    """
    if holdings is None:
        holdings = collect_npc_holdings(save)
    if not holdings:
        return {}
    moved = {}
    for code, v in holdings.items():
        stock = save.find(code)
        if stock is None:
            continue
        clear_npc_stock_positions(save, code)
        ret_d = stock._d["Retail"][0]
        ret_d["VolumeUsableSell"] = int(ret_d.get("VolumeUsableSell", 0)) + v
        moved[code] = v
        # 平账：保证 主力+散户+NPC+玩家 == 流通股（全内部值精确运算）
        try:
            _flow = int(stock.info._d.get("VolumeFlow", 0))
            inst_d = stock._d["Institution"][0]
            iv = int(inst_d.get("VolumeUsableSell", 0))
            rv = int(ret_d.get("VolumeUsableSell", 0))
            npc_sum = _npc_positions(save, code)
            p_vol = 0
            for _p in save.player._d.get("StockPos", []) or []:
                if _p.get("Code") == code:
                    p_vol += int(_p.get("VolumeUsable", 0))
            total = iv + rv + npc_sum + p_vol
            delta = total - _flow
            if delta > 0:
                remain = delta
                take = min(rv, remain); ret_d["VolumeUsableSell"] = rv - take; remain -= take
                take = min(int(inst_d.get("VolumeUsableSell", 0)), remain); inst_d["VolumeUsableSell"] = int(inst_d.get("VolumeUsableSell", 0)) - take; remain -= take
                if remain > 0:
                    stock.info._d["VolumeFlow"] = _flow + remain
                    if "VolumeFlowInit" in stock.info._d:
                        stock.info._d["VolumeFlowInit"] = stock.info._d["VolumeFlow"]
            elif delta < 0:
                inst_d["VolumeUsableSell"] = int(inst_d.get("VolumeUsableSell", 0)) + (-delta)
        except Exception:
            # 平账失败不应阻断主流程；调用方据摘要决定如何提示
            pass
    return moved


# [extra]
def rectify_market(save):
    """逐只股票强制 主力+散户+NPC+玩家 == VolumeFlow 的筹码守恒修正。

    save: SaveModel。
    策略：差异<10000 按「散户→主力→NPC→玩家」顺序扣减；差异≥10000 按比例缩放；
    差异为负补主力；最后兜底改 VolumeFlow 兜平。返回 {code: 说明} 摘要。
    全程内部值精确整数运算。
    """
    keys = NPC_KEYS
    summary = {}
    for stock in save.stocks:
        info_d = stock.info._d
        code = info_d["Code"]
        flow = int(info_d.get("VolumeFlow", 0))
        inst_d = stock._d["Institution"][0]
        ret_d = stock._d["Retail"][0]
        p_v = 0
        for p in save.player._d.get("StockPos", []) or []:
            if p.get("Code") == code:
                p_v += int(p.get("VolumeUsable", 0))
        iv = int(inst_d.get("VolumeUsableSell", 0))
        rv = int(ret_d.get("VolumeUsableSell", 0))
        npc_v = {}
        for k in keys:
            v = 0
            for acc in save.npc_account_list(k):
                for p in acc.get("StockPos", []) or []:
                    if p.get("Code") == code:
                        v += int(p.get("VolumeUsable", 0))
            npc_v[k] = v
        sh = p_v + iv + rv + sum(npc_v.values())
        diff = sh - flow
        if diff == 0:
            summary[code] = "平衡"
            continue
        if abs(diff) < 10000:
            if diff > 0:
                take = diff
                for (name, setter_fn) in [("ret", lambda v: ret_d.__setitem__("VolumeUsableSell", v)),
                                          ("inst", lambda v: inst_d.__setitem__("VolumeUsableSell", v))]:
                    cur = int(ret_d.get("VolumeUsableSell", 0)) if name == "ret" else int(inst_d.get("VolumeUsableSell", 0))
                    t = min(cur, take); setter_fn(cur - t); take -= t
                if take > 0:
                    for k in keys:
                        for acc in save.npc_account_list(k):
                            for p in acc.get("StockPos", []) or []:
                                if p.get("Code") == code and take > 0:
                                    cv = int(p.get("VolumeUsable", 0))
                                    t = min(cv, take); p["VolumeUsable"] = cv - t; take -= t
                if take > 0:
                    for p in save.player._d.get("StockPos", []) or []:
                        if p.get("Code") == code and take > 0:
                            cv = int(p.get("VolumeUsable", 0))
                            t = min(cv, take); p["VolumeUsable"] = cv - t; take -= t
                summary[code] = "顺序扣 " + str(diff - take)
            else:
                need = -diff
                inst_d["VolumeUsableSell"] = iv + need
                summary[code] = "主力加 " + str(need)
        else:
            if sh > 0:
                scale = flow / sh
                tot = 0
                inst_d["VolumeUsableSell"] = int(iv * scale); tot += inst_d["VolumeUsableSell"]
                ret_d["VolumeUsableSell"] = int(rv * scale); tot += ret_d["VolumeUsableSell"]
                for k in keys:
                    for acc in save.npc_account_list(k):
                        for p in acc.get("StockPos", []) or []:
                            if p.get("Code") == code:
                                ov = int(p.get("VolumeUsable", 0))
                                p["VolumeUsable"] = int(ov * scale); tot += int(ov * scale)
                for p in save.player._d.get("StockPos", []) or []:
                    if p.get("Code") == code:
                        ov = int(p.get("VolumeUsable", 0))
                        p["VolumeUsable"] = int(ov * scale); tot += int(ov * scale)
                err = flow - tot
                if err != 0:
                    for p in save.player._d.get("StockPos", []) or []:
                        if p.get("Code") == code:
                            p["VolumeUsable"] = int(p.get("VolumeUsable", 0)) + err
                            break
                summary[code] = "比例修正 scale=" + str(round(scale, 4))
    # 兜底：仍不平衡的直接改 VolumeFlow
    for stock in save.stocks:
        info_d = stock.info._d
        code = info_d["Code"]
        flow = int(info_d.get("VolumeFlow", 0))
        sh = int(stock._d["Institution"][0].get("VolumeUsableSell", 0)) + int(stock._d["Retail"][0].get("VolumeUsableSell", 0))
        for k in keys:
            for acc in save.npc_account_list(k):
                for p in acc.get("StockPos", []) or []:
                    if p.get("Code") == code:
                        sh += int(p.get("VolumeUsable", 0))
        for p in save.player._d.get("StockPos", []) or []:
            if p.get("Code") == code:
                sh += int(p.get("VolumeUsable", 0))
        if sh != flow:
            info_d["VolumeFlow"] = sh
            if "VolumeFlowInit" in info_d:
                info_d["VolumeFlowInit"] = sh
    return summary
