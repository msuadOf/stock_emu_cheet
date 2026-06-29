"""[extra] 公告 / 业绩报告相关纯核心（社区贡献 extra 功能）。

从原 TUI 的 ``_build_stock_notice`` / ``_append_notice_normal`` /
``get_current_game_day`` / ``get_or_create_delisted_pool`` /
``_filter_delisted_candidates`` / ``_create_stock_performance`` 中剥离
「构造数据 + 写入存档」的纯部分；交互（prompt/print/confirm）仍留 TUI。

**已迁移到 SaveModel**：函数收 ``SaveModel``/``StockModel``/``InfoModel``，全程用
getter/setter（显示值）。×100 换算由 model 在边界处理，业务代码不再手写 /100 或 ×100。
业绩报告(NoticeReport) 内部仍存「内部值」（与存档约定一致），故报告的财务字段读
``*_raw``、写回 Info 时用 setter（收显示值，内部 ×100）。

无 I/O、无交互副作用。标记统一为 ``# [extra]``。
"""

# [extra] extra 功能（社区贡献），非原主干。


def get_current_game_day(stock):
    """从 K 线最后一根取当前游戏天数；无 K 线返回 0。stock: StockModel。"""
    candles = stock.info._d.get("Candles", [])
    if candles:
        return candles[-1].get("Day", 0)
    return 0


# [extra]
def get_or_create_delisted_pool(save):
    """确保 Market.DelistedPool = {A:[], B:[]} 存在且结构正确；返回它。save: SaveModel。"""
    return save.get_or_create_delisted_pool()


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
def append_notice_normal(save, notice_list):
    """把一批 NoticeNormal 公告写入 NoticeGroup.NoticeNormal（移除临时 _ 字段）。

    确保 NoticeNormal/NoticeRank/NoticeReport 三键存在。save: SaveModel。
    """
    m = save._d.setdefault("Market", {})
    ng = m.get("NoticeGroup")
    if not isinstance(ng, dict):
        ng = {}
        m["NoticeGroup"] = ng
    for key in ("NoticeNormal", "NoticeRank", "NoticeReport"):
        if key not in ng:
            ng[key] = []
    for n in notice_list:
        nn = {k: v for k, v in n.items() if not k.startswith("_")}
        ng["NoticeNormal"].append(nn)
    return len(notice_list)


# [extra]
def filter_delisted_candidates(save):
    """筛选退市候选：负债率>80% 且最近 5 条业绩报告净利润均为负。

    save: SaveModel。返回 [(code, debt_ratio, report_count), ...]。
    负债率 debt_ratio 由 InfoModel.debt_ratio 给出（小数 0~1），这里转成百分数。
    """
    ng = save._d.get("Market", {}).get("NoticeGroup", {})
    reports = ng.get("NoticeReport", []) if isinstance(ng, dict) else []
    by_code = {}
    for r in reports:
        c = r.get("Code")
        if c is None:
            continue
        by_code.setdefault(c, []).append(r)

    candidates = []
    for stock in save.stocks:
        info = stock.info
        code = info.code
        dr_pct = info.debt_ratio * 100
        if dr_pct <= 80:
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
            # 报告财务字段是内部值；净利润符号与是否除以 100 无关，直接比符号即可
            nb = r.get("RewardBusiness", 0) + r.get("RewardOther", 0) - r.get("CostBusiness", 0) - r.get("CostOther", 0)
            if nb >= 0:
                all_neg = False
                break
        if all_neg:
            candidates.append((code, dr_pct, len(recent)))
    return candidates


# [extra]
def build_performance_report(code, info, notice_day, star, report_strength, is_buy,
                             asset_net, asset_loan, reward_business, reward_other,
                             cost_business, cost_other):
    """构建一条业绩报告(NoticeReport) dict（不写入存档）。

    info: InfoModel（Prev 字段取自当前 info 的内部值）。
    传入的 asset_net/asset_loan/reward_*/cost_* 是**显示值**（元），写入报告时
    存**内部值**（×100）以与存档约定一致。
    Prob = Star * ReportStrength；ReduceProb = 1/Star (Star>0 时)。
    """
    prob = star * report_strength
    reduce_prob = (1.0 / star) if star > 0 else 0
    # Prev 取当前内部值（报告里 Prev 与当前同字段同为内部值）。AssetNet 等用 _Scaled
    # 描述符（无 *_raw），故直接读内部 dict 树。
    d = info._d
    return {
        "Code": code,
        "Buy": is_buy,
        "Star": star,
        "ReduceProb": reduce_prob,
        "Prob": prob,
        "Day": notice_day,
        "AssetNetPrev": d.get("AssetNet", 0), "AssetNet": int(round(asset_net * 100)),
        "AssetLoanPrev": d.get("AssetLoan", 0), "AssetLoan": int(round(asset_loan * 100)),
        "RewardBusinessPrev": d.get("RewardBusiness", 0), "RewardBusiness": int(round(reward_business * 100)),
        "RewardOtherPrev": d.get("RewardOther", 0), "RewardOther": int(round(reward_other * 100)),
        "CostBusinessPrev": d.get("CostBusiness", 0), "CostBusiness": int(round(cost_business * 100)),
        "CostOtherPrev": d.get("CostOther", 0), "CostOther": int(round(cost_other * 100)),
    }


# [extra]
def commit_performance_report(save, report):
    """把业绩报告写入 NoticeGroup.NoticeReport，并把 Info 财务字段同步为报告当前值，
    重算 NetProfit/DebtRatio/PE/PB。save: SaveModel。

    报告里的财务字段是**内部值**，Info 用 setter（收显示值）写入。
    """
    code = report["Code"]
    stock = save.find(code)
    if stock is None:
        return False
    info = stock.info

    m = save._d.setdefault("Market", {})
    ng = m.get("NoticeGroup")
    if not isinstance(ng, dict):
        ng = {}
        m["NoticeGroup"] = ng
    for key in ("NoticeNormal", "NoticeRank", "NoticeReport"):
        if key not in ng:
            ng[key] = []
    ng["NoticeReport"].append(report)

    # 报告字段是内部值；用 setter（收显示值，内部 ×100）写入，等价回写内部值
    info.asset_net = report["AssetNet"] / 100
    info.asset_loan = report["AssetLoan"] / 100
    info.reward_business = report["RewardBusiness"] / 100
    info.reward_other = report["RewardOther"] / 100
    info.cost_business = report["CostBusiness"] / 100
    info.cost_other = report["CostOther"] / 100
    # NetProfit/DebtRatio/PE/PB 是 Info 上的派生字段（非 ×100 的展示值），直接写内部树
    net_profit = report["RewardBusiness"] + report["RewardOther"] - report["CostBusiness"] - report["CostOther"]
    info._d["NetProfit"] = net_profit
    total_assets = report["AssetNet"] + report["AssetLoan"]
    info._d["DebtRatio"] = report["AssetLoan"] / total_assets if total_assets else 0
    # PE/PB 按存档×100缩放规则: 现价*VolumeTotal/(100*NetProfit)，全用内部值。
    # 现价取最后 K 线 Close（与 calc_pe/pb 同源），不是陈旧的 PriceFact。
    price = info.last_close_raw
    volume_total = info.volume_total_raw
    info._d["PE"] = (price * volume_total / (100 * net_profit)) if net_profit else 0
    info._d["PB"] = (price * volume_total / (100 * report["AssetNet"])) if report["AssetNet"] else 0
    return True
