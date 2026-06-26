"""[extra] 分红 / 定向增发 / 退市 相关纯核心（社区贡献 extra 功能）。

把原 TUI 的 ``stock_dividend`` / ``private_placement`` / ``delist_stock`` 中
「计算 + 改存档」的纯部分剥离；交互（prompt/print/confirm）与 Name.sav 落盘留 TUI。
新股发行(issue_stock)的纯构造/挂载函数见 build_new_stock_* / attach_stock_to_market。

标记统一为 ``# [extra]``。单位换算（×100）与原代码一致。
"""
from .market_ops import NPC_KEYS, _npc_positions, clear_npc_stock_positions

# [extra] extra 功能（社区贡献），非原主干。


# ------------------------------------------------------------------
# 现金分红：do_cash 的纯部分
# ------------------------------------------------------------------
def cash_dividend_limits(info, total_hand):
    """计算现金分红上限（内部单位）。

    max_total_by_debt = max(0, 总资产×70% - 总负债)
    max_total_by_asset = max(0, 净资产)
    max_total = min(两者)
    max_D = max_total * 10000 // total_hand   (每手分红的「内部」上限)
    返回 (max_total, max_D)。
    """
    asset_net = info.get("AssetNet", 0)
    asset_loan = info.get("AssetLoan", 0)
    total_asset = asset_net + asset_loan
    max_total_by_debt = max(0, int(total_asset * 0.70) - asset_loan)
    max_total_by_asset = max(0, int(asset_net))
    max_total = min(max_total_by_debt, max_total_by_asset)
    max_D = (max_total * 10000 // total_hand) if total_hand > 0 else 0
    return max_total, max_D


# [extra]
def apply_cash_dividend(e, code, stock, vols, D_int):
    """执行现金分红：把 D 分发到所有持仓者、除息降股价、扣减净资产、发业绩报告。

    - vols: {账户键: 持仓量}（含 'player'/'inst'/'ret' + 5 类 NPC）
    - D_int: 每手分红(元/100股) × 100 后的整数（即「分」）
    返回 total_div(总分红, 内部元)。调用方需先校验 D_int <= max_D。
    """
    info = stock["Info"]
    s = stock
    total_hand = sum(int(v) for v in vols.values())
    total_div = total_hand * D_int // 10000  # 内部元

    for k, vol in vols.items():
        add = int(vol) * D_int // 10000
        if add == 0:
            continue
        if k == "player":
            e.data["Player"]["Amount"] = int(e.data["Player"].get("Amount", 0)) + add
            e.data["Player"]["AmountInit"] = int(e.data["Player"].get("AmountInit", 0)) + add
        elif k == "inst":
            s["Institution"][0]["AmountUsableBuy"] = int(s["Institution"][0].get("AmountUsableBuy", 0)) + add
        elif k == "ret":
            s["Retail"][0]["AmountUsableBuy"] = int(s["Retail"][0].get("AmountUsableBuy", 0)) + add
        else:
            for acc in e.data["Market"].get(k, []) or []:
                for p in acc.get("StockPos", []) or []:
                    if p.get("Code") == code:
                        acc["Amount"] = int(acc.get("Amount", 0)) + int(p.get("VolumeUsable", 0)) * D_int // 10000
    # 除息：降股价 + 扣净资产（不动总股本/流通股）
    # 原代码 new_price = max(1, int(price) - int(D))，D 即传入的 D_int(分)，PriceFact 以分计
    price = info.get("PriceFact", 0)
    asset_net = info.get("AssetNet", 0)
    asset_loan = info.get("AssetLoan", 0)
    new_price = max(1, int(price) - int(D_int))
    info["PriceFact"] = new_price
    info["AssetNet"] = max(0, int(asset_net) - total_div)
    info["AssetNetPrev"] = info["AssetNet"]
    info["AssetLoanPrev"] = int(asset_loan)
    e.modified = True
    return total_div


# ------------------------------------------------------------------
# 送股：do_stock 的纯部分
# ------------------------------------------------------------------
# [extra]
def apply_stock_dividend(e, code, stock, X):
    """执行送股(10送X)：按比例增加所有持仓、股价等比下降、总市值不变。

    返回 (new_flow, new_total, new_price)。
    """
    info = stock["Info"]
    flow = info.get("VolumeFlow", 0)
    total_shares = info.get("VolumeTotal", 0)
    price = info.get("PriceFact", 0)
    r = 1 + X / 10.0
    nf = int(flow * r)
    nt = int(total_shares * r)
    np2 = int(price / r)
    info["VolumeFlow"] = nf
    info["VolumeTotal"] = nt
    info["PriceFact"] = np2
    if "VolumeFlowInit" in info:
        info["VolumeFlowInit"] = nf
    # 玩家持仓同比例放大
    for p in e.data["Player"].get("StockPos", []) or []:
        if p.get("Code") == code:
            old = int(p.get("VolumeUsable", 0))
            p["VolumeUsable"] = int(old * r)
            if price:
                p["Amount"] = int(p.get("Amount", 0) * np2 / price)
    # 主力
    iv = int(stock["Institution"][0].get("VolumeUsableSell", 0))
    stock["Institution"][0]["VolumeUsableSell"] = int(iv * r)
    stock["Institution"][0]["InitVolumeSell"] = stock["Institution"][0]["VolumeUsableSell"]
    # 散户
    rv = int(stock["Retail"][0].get("VolumeUsableSell", 0))
    stock["Retail"][0]["VolumeUsableSell"] = int(rv * r)
    # NPC
    for k in NPC_KEYS:
        for acc in e.data["Market"].get(k, []) or []:
            for p in acc.get("StockPos", []) or []:
                if p.get("Code") == code:
                    ov = int(p.get("VolumeUsable", 0))
                    p["VolumeUsable"] = int(ov * r)
                    if price:
                        p["Amount"] = int(p.get("Amount", 0) * np2 / price)
    e.modified = True
    return nf, nt, np2


# ------------------------------------------------------------------
# 定向增发：private_placement 的纯部分
# ------------------------------------------------------------------
# [extra]
def compute_placement(candles, price_fact, ratio, amount_yuan):
    """计算定向增发的发行价/新增股数。

    返回 (avg20, py_元, pi_内部, ns_内部股, cost_内部元)。
    - avg20: 近20日均价(元/股)；K线不足用 PriceFact/100
    - py: 发行价(元) = avg20*ratio
    - pi: 发行价内部值 = py*100
    - ns: 新增内部股 = amount_yuan/py*100
    - cost: 玩家支付内部元 = amount_yuan*100
    """
    last20 = candles[-20:] if len(candles) >= 20 else candles
    if not last20:
        avg20 = price_fact / 100
    else:
        avg20 = sum(int(c.get("Close", 0)) for c in last20) / 100.0 / len(last20)
    py = avg20 * ratio
    pi = int(py * 100)
    ns = int(amount_yuan / py * 100)
    cost = int(amount_yuan * 100)
    return avg20, py, pi, ns, cost


# [extra]
def apply_private_placement(e, code, stock, ns, cost, candles):
    """执行定向增发：新增流通/总股本、扣玩家资金、登记持仓/交易记录。返回 ns。

    调用方需先校验 ns > 0。
    """
    info = stock["Info"]
    info["VolumeFlow"] = int(info.get("VolumeFlow", 0)) + ns
    info["VolumeTotal"] = int(info.get("VolumeTotal", 0)) + ns
    if "VolumeFlowInit" in info:
        info["VolumeFlowInit"] = info["VolumeFlow"]
    player = e.data["Player"]
    player["Amount"] = int(player.get("Amount", 0)) - cost
    player["AmountInit"] = int(player.get("AmountInit", 0)) - cost
    entry = None
    for p in player.get("StockPos", []) or []:
        if p.get("Code") == code:
            entry = p
            break
    if entry is None:
        entry = {"Code": code, "Amount": 0, "VolumeUsable": 0}
        player["StockPos"].append(entry)
    prev = int(entry.get("VolumeUsable", 0))
    entry["VolumeUsable"] = prev + ns
    entry["Amount"] = int(entry.get("Amount", 0)) + cost
    if prev == 0:
        opt = player.get("Optional", [])
        if code not in opt:
            opt.append(code)
        tt = player.get("TradeType", [])
        day = 1
        if candles:
            day = candles[-1].get("Day", 0) + 1
        tt.append({"Code": code, "Day": day, "Type": 1})
    e.modified = True
    return ns


# ------------------------------------------------------------------
# 退市：delist_stock 各步纯核心
# ------------------------------------------------------------------
# [extra]
def remove_stock_from_market(e, code):
    """从股票池删除某 code；返回被删的 stock（或 None）。"""
    removed = None
    new_stocks = []
    for s in e.data["Market"]["Stocks"]:
        if s["Info"]["Code"] == code:
            removed = s
        else:
            new_stocks.append(s)
    e.data["Market"]["Stocks"] = new_stocks
    return removed


# [extra]
def remove_code_notices(e, code):
    """从 NoticeGroup 中删除某 code 的所有公告（兼容 dict/list 两种形态）。"""
    ng = e.data["Market"].get("NoticeGroup", {})
    if isinstance(ng, dict):
        for key in list(ng.keys()):
            ng[key] = [item for item in ng[key] if item.get("Code") != code]
    elif isinstance(ng, list):
        e.data["Market"]["NoticeGroup"] = [item for item in ng if item.get("Code") != code]


# [extra]
def remove_player_position(e, code):
    """删除玩家某 code 的持仓；返回 [(Amount, VolumeUsable)] 便于估算亏损。"""
    sp = e.data["Player"].get("StockPos", [])
    removed = [(p.get("Amount", 0), p.get("VolumeUsable", 0))
               for p in sp if p.get("Code") == code]
    e.data["Player"]["StockPos"] = [p for p in sp if p.get("Code") != code]
    return removed


# [extra]
def delist_to_b(e, code):
    """完全退市(进 B 集合)：从股票池删除、清公告、删玩家持仓、A 移出/B 加入。
    返回 (removed_stock, player_positions)。"""
    pool = __import__("src.core.extra.notice_ops", fromlist=["get_or_create_delisted_pool"]).get_or_create_delisted_pool(e)
    a_set = pool["A"]
    b_set = pool["B"]
    stock = remove_stock_from_market(e, code)
    remove_code_notices(e, code)
    positions = remove_player_position(e, code)
    if code in a_set:
        a_set.remove(code)
    if code not in b_set:
        b_set.append(code)
    e.modified = True
    return stock, positions


# [extra]
def delist_to_a(e, code, rate_limit=0.05):
    """警告退市(进 A 集合)：限制 RateLimit，加入 A 集合。返回是否成功。"""
    pool = __import__("src.core.extra.notice_ops", fromlist=["get_or_create_delisted_pool"]).get_or_create_delisted_pool(e)
    a_set = pool["A"]
    stock = e.find(code)
    if not stock:
        return False
    stock["Info"]["RateLimit"] = rate_limit
    if code not in a_set:
        a_set.append(code)
    e.modified = True
    return True


# ------------------------------------------------------------------
# 新股发行：issue_stock 的纯构造/挂载部分
# ------------------------------------------------------------------
# [extra]
def build_new_stock_restore(new_code, sector_limit, sector_rate_limit,
                            volume_total, volume_flow, asset_net, asset_loan,
                            reward_business, reward_other, cost_business, cost_other,
                            net_profit, raw_price, bourse_num, sector_num):
    """构造「退市池恢复」模式的新股 dict（无主力/散户初始持仓）。"""
    return {
        "Info": {
            "Code": new_code, "Limit": sector_limit, "RateLimit": sector_rate_limit,
            "VolumeTotal": volume_total, "VolumeFlow": volume_flow, "VolumeFlowInit": volume_flow,
            "AssetNet": asset_net, "AssetNetPrev": asset_net,
            "AssetLoan": asset_loan, "AssetLoanPrev": asset_loan,
            "RewardBusiness": reward_business, "RewardBusinessPrev": reward_business,
            "RewardOther": reward_other, "RewardOtherPrev": reward_other,
            "CostBusiness": cost_business, "CostBusinessPrev": cost_business,
            "CostOther": cost_other, "CostOtherPrev": cost_other,
            "ProfitNetPrev": net_profit,
            "PriceInit": raw_price, "PriceFact": raw_price,
            "Bourse": bourse_num, "Sector": sector_num, "Candles": [],
        },
        "Institution": [{"VolumeUsableSell": 0, "AmountUsableBuy": 0, "InitVolumeSell": 0, "InitAmountBuy": 0, "Pos": [], "PosSell": [], "PosBuy": []}],
        "Retail": [{"VolumeUsableSell": 0, "AmountUsableBuy": 0}],
    }


# [extra]
def build_new_stock_custom(new_code, default_info, total_shares_internal, floats_internal,
                           raw_price, inst_vol_internal, inst_buy, retail_vol_internal, retail_buy,
                           bourse_num, sector_num):
    """构造「自定义发行」模式的新股 dict（主力51%/散户49% 初始持仓）。"""
    return {
        "Info": {
            "Code": new_code,
            "Limit": default_info.get("Limit", True),
            "RateLimit": default_info.get("RateLimit", 0.10),
            "VolumeTotal": total_shares_internal, "VolumeFlow": floats_internal, "VolumeFlowInit": floats_internal,
            "AssetNet": default_info.get("AssetNet", 0), "AssetNetPrev": default_info.get("AssetNet", 0),
            "AssetLoan": default_info.get("AssetLoan", 0), "AssetLoanPrev": default_info.get("AssetLoan", 0),
            "RewardBusiness": default_info.get("RewardBusiness", 0), "RewardBusinessPrev": default_info.get("RewardBusiness", 0),
            "RewardOther": default_info.get("RewardOther", 0), "RewardOtherPrev": default_info.get("RewardOther", 0),
            "CostBusiness": default_info.get("CostBusiness", 0), "CostBusinessPrev": default_info.get("CostBusiness", 0),
            "CostOther": default_info.get("CostOther", 0), "CostOtherPrev": default_info.get("CostOther", 0),
            "ProfitNetPrev": (default_info.get("RewardBusiness", 0) + default_info.get("RewardOther", 0)
                              - default_info.get("CostBusiness", 0) - default_info.get("CostOther", 0)),
            "PriceInit": raw_price, "PriceFact": raw_price,
            "Bourse": bourse_num, "Sector": sector_num, "Candles": [],
        },
        "Institution": [{
            "VolumeUsableSell": inst_vol_internal, "AmountUsableBuy": inst_buy,
            "InitVolumeSell": inst_vol_internal, "InitAmountBuy": inst_buy,
            "Pos": [], "PosSell": [], "PosBuy": [],
        }],
        "Retail": [{"VolumeUsableSell": retail_vol_internal, "AmountUsableBuy": retail_buy}],
    }


# [extra]
def attach_stock_to_market(e, new_stock, raw_price, sector_num, bourse_num,
                           mode="restore", restore_code=None):
    """把构造好的新股挂接到市场：生成初始 K 线、加入股票池、挂接 Sectors、
    （恢复模式）从退市池 B 移除 code。返回 new_stock。"""
    init_volume = max(1, int(new_stock["Info"].get("VolumeFlow", 0) / 10000))
    init_candle = {
        "Day": 1, "Open": raw_price, "Close": raw_price,
        "High": raw_price, "Low": raw_price,
        "Volume": init_volume, "Amount": init_volume * raw_price,
    }
    new_stock["Info"]["Candles"] = [init_candle]
    e.data["Market"]["Stocks"].append(new_stock)

    sectors = e.data["Market"].get("Sectors")
    if not isinstance(sectors, list):
        sectors = []
    e.data["Market"]["Sectors"] = sectors
    new_code = new_stock["Info"]["Code"]
    for sector_code in (sector_num, int(bourse_num)):
        found = None
        for s_obj in sectors:
            if isinstance(s_obj, dict) and s_obj.get("Code") == sector_code:
                found = s_obj
                break
        if found is None:
            found = {"Code": sector_code, "StockCodes": []}
            sectors.append(found)
        stock_codes = found.get("StockCodes")
        if not isinstance(stock_codes, list):
            stock_codes = []
            found["StockCodes"] = stock_codes
        if new_code not in stock_codes:
            stock_codes.append(new_code)

    if mode == "restore" and restore_code is not None:
        pool = __import__("src.core.extra.notice_ops", fromlist=["get_or_create_delisted_pool"]).get_or_create_delisted_pool(e)
        if restore_code in pool["B"]:
            pool["B"].remove(restore_code)
    e.modified = True
    return new_stock
