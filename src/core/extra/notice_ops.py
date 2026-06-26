"""[extra] 公告 / 业绩报告相关纯核心（社区贡献 extra 功能）。

从原 TUI 的 ``_build_stock_notice`` / ``_append_notice_normal`` /
``get_current_game_day`` / ``get_or_create_delisted_pool`` /
``_filter_delisted_candidates`` / ``_create_stock_performance`` 中剥离
「构造数据 + 写入存档」的纯部分；交互（prompt/print/confirm）仍留 TUI。

无 I/O、无交互副作用。标记统一为 ``# [extra]``。
"""

# [extra] extra 功能（社区贡献），非原主干。


def get_current_game_day(stock):
    """从 K 线最后一根取当前游戏天数；无 K 线返回 0。"""
    info = stock["Info"]
    candles = info.get("Candles", [])
    if candles:
        return candles[-1].get("Day", 0)
    return 0


# [extra]
def get_or_create_delisted_pool(e):
    """确保 Market.DelistedPool = {A:[], B:[]} 存在且结构正确；返回它。"""
    if "DelistedPool" not in e.data["Market"] or not isinstance(e.data["Market"]["DelistedPool"], dict):
        e.data["Market"]["DelistedPool"] = {"A": [], "B": []}
    pool = e.data["Market"]["DelistedPool"]
    if "A" not in pool or not isinstance(pool["A"], list):
        pool["A"] = []
    if "B" not in pool or not isinstance(pool["B"], list):
        pool["B"] = []
    return pool


# [extra]
def build_stock_notice(code, notice_day, star, strength=1.0, create_prob=0.08):
    """构建单条股票公告(NoticeNormal) dict（不写入存档）。

    Prob = Star * strength
    ReduceProb = create_prob / Star  (Star>0 时；否则 0)
    """
    prob = star * strength
    reduce_prob = create_prob / star if star > 0 else 0
    return {
        "Code": code,
        "Buy": True,
        "Star": star,
        "ReduceProb": reduce_prob,
        "Prob": prob,
        "Day": notice_day,
        "_strength": strength,
        "_create_prob": create_prob,
    }


# [extra]
def append_notice_normal(e, notice_list):
    """把一批 NoticeNormal 公告写入 NoticeGroup.NoticeNormal（移除临时 _ 字段）。

    确保 NoticeNormal/NoticeRank/NoticeReport 三键存在。置 e.modified=True。
    """
    ng = e.data["Market"].get("NoticeGroup", {})
    if not isinstance(ng, dict):
        ng = {}
        e.data["Market"]["NoticeGroup"] = ng
    for key in ("NoticeNormal", "NoticeRank", "NoticeReport"):
        if key not in ng:
            ng[key] = []
    for n in notice_list:
        nn = {k: v for k, v in n.items() if not k.startswith("_")}
        ng["NoticeNormal"].append(nn)
    e.modified = True
    return len(notice_list)


# [extra]
def filter_delisted_candidates(e):
    """筛选退市候选：负债率>80% 且最近 5 条业绩报告净利润均为负。

    返回 [(code, debt_ratio, report_count), ...]。
    """
    ng = e.data["Market"].get("NoticeGroup", {})
    reports = ng.get("NoticeReport", []) if isinstance(ng, dict) else []
    by_code = {}
    for r in reports:
        c = r.get("Code")
        if c is None:
            continue
        by_code.setdefault(c, []).append(r)

    candidates = []
    for s in e.stocks():
        code = s["Info"].get("Code")
        info = s["Info"]
        asset_net = info.get("AssetNet", 0)
        asset_loan = info.get("AssetLoan", 0)
        total = asset_net + asset_loan
        dr = (asset_loan / total * 100) if total > 0 else 0
        if dr <= 80:
            continue
        rs = by_code.get(code, [])
        if not rs:
            continue
        rs_sorted = sorted(rs, key=lambda x: x.get("Day", 0), reverse=True)
        recent = rs_sorted[:5]
        if len(recent) < 5:
            continue
        all_neg = True
        for r in recent:
            nb = r.get("RewardBusiness", 0) + r.get("RewardOther", 0) - r.get("CostBusiness", 0) - r.get("CostOther", 0)
            if nb >= 0:
                all_neg = False
                break
        if all_neg:
            candidates.append((code, dr, len(recent)))
    return candidates


# [extra]
def build_performance_report(code, info, notice_day, star, report_strength, is_buy,
                             asset_net, asset_loan, reward_business, reward_other,
                             cost_business, cost_other):
    """构建一条业绩报告(NoticeReport) dict（不写入存档）。

    Prob = Star * ReportStrength；ReduceProb = 1/Star (Star>0 时)。
    Prev 字段取自当前 info 的原值。
    """
    prob = star * report_strength
    reduce_prob = (1.0 / star) if star > 0 else 0
    return {
        "Code": code,
        "Buy": is_buy,
        "Star": star,
        "ReduceProb": reduce_prob,
        "Prob": prob,
        "Day": notice_day,
        "AssetNetPrev": info.get("AssetNet", 0), "AssetNet": asset_net,
        "AssetLoanPrev": info.get("AssetLoan", 0), "AssetLoan": asset_loan,
        "RewardBusinessPrev": info.get("RewardBusiness", 0), "RewardBusiness": reward_business,
        "RewardOtherPrev": info.get("RewardOther", 0), "RewardOther": reward_other,
        "CostBusinessPrev": info.get("CostBusiness", 0), "CostBusiness": cost_business,
        "CostOtherPrev": info.get("CostOther", 0), "CostOther": cost_other,
    }


# [extra]
def commit_performance_report(e, report):
    """把业绩报告写入 NoticeGroup.NoticeReport，并把 Info 财务字段同步为报告当前值，
    重算 NetProfit/DebtRatio/PE/PB。置 e.modified=True。"""
    code = report["Code"]
    stock = e.find(code)
    if stock is None:
        return False
    info = stock["Info"]

    ng = e.data["Market"].get("NoticeGroup", {})
    if not isinstance(ng, dict):
        ng = {}
        e.data["Market"]["NoticeGroup"] = ng
    for key in ("NoticeNormal", "NoticeRank", "NoticeReport"):
        if key not in ng:
            ng[key] = []
    ng["NoticeReport"].append(report)

    asset_net = report["AssetNet"]
    asset_loan = report["AssetLoan"]
    reward_business = report["RewardBusiness"]
    reward_other = report["RewardOther"]
    cost_business = report["CostBusiness"]
    cost_other = report["CostOther"]
    info["AssetNet"] = asset_net
    info["AssetLoan"] = asset_loan
    info["RewardBusiness"] = reward_business
    info["RewardOther"] = reward_other
    info["CostBusiness"] = cost_business
    info["CostOther"] = cost_other
    net_profit = (reward_business + reward_other) - (cost_business + cost_other)
    info["NetProfit"] = net_profit
    total_assets = asset_net + asset_loan
    info["DebtRatio"] = asset_loan / total_assets if total_assets else 0
    price_fact = info.get("PriceFact", 0)
    volume_total = info.get("VolumeTotal", 0)
    info["PE"] = (price_fact * volume_total / (100 * net_profit)) if net_profit else 0
    info["PB"] = (price_fact * volume_total / (100 * asset_net)) if asset_net else 0
    e.modified = True
    return True
