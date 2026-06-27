"""单只股票的主干编辑操作（纯函数，无 I/O、无交互）。

这些是把原 TUI 的 ``change_*`` 函数里「计算 + 改数据」的部分剥离出来的纯核心，
供 CLI / GUI / TUI 共享。TUI 的 wrapper 负责收输入/打印/确认，再调这里的函数。

单位换算（×100）与原代码一致：价格/股数/金额的内部值 = 显示值 × 100。
"""
from .calcs import calc_pe, calc_pb


# ------------------------------------------------------------------
# 估值：PE / PB / 负债率
# ------------------------------------------------------------------
def set_target_pe(info, target):
    """按目标 PE 反推净利润并写入（同时清零成本、同步 Prev/Min）。

    PE = PriceFact * VolumeTotal / (100 * NetProfit)  =>
        NetProfit = PriceFact * VolumeTotal / (100 * target)

    返回写入的净利润值。
    """
    p = info["PriceFact"]
    v = info["VolumeTotal"]
    target_np = p * v / (100 * target)
    info["RewardBusiness"] = int(target_np)
    info["RewardOther"] = 0
    info["CostBusiness"] = 0
    info["CostOther"] = 0
    info["ProfitNetPrev"] = int(target_np)
    for k in ("RewardBusinessPrev", "RewardOtherPrev", "CostBusinessPrev", "CostOtherPrev"):
        if k in info:
            info[k] = int(target_np) if "Reward" in k else 0
    for k in ("RewardBusinessMin", "RewardOtherMin", "CostBusinessMin", "CostOtherMin"):
        if k in info:
            info[k] = 0
    return int(target_np)


def set_target_pb(info, target):
    """按目标 PB 反推净资产并写入（同步 Prev，Min 归零）。返回新净资产。"""
    p = info["PriceFact"]
    v = info["VolumeTotal"]
    target_an = p * v / (100 * target)
    info["AssetNet"] = int(target_an)
    if "AssetNetPrev" in info:
        info["AssetNetPrev"] = int(target_an)
    if "AssetNetMin" in info:
        info["AssetNetMin"] = 0
    return int(target_an)


def set_target_debt_ratio(info, target_pct):
    """按目标负债率(百分数)反推 AssetLoan 并写入。返回新 AssetLoan。

    负债率 = AssetLoan / (AssetLoan + AssetNet) * 100%
        =>  AssetLoan = AssetNet * target / (100 - target)
    """
    new_loan = info["AssetNet"] * target_pct / (100 - target_pct)
    info["AssetLoan"] = int(new_loan)
    if "AssetLoanPrev" in info:
        info["AssetLoanPrev"] = int(new_loan)
    if "AssetLoanMin" in info:
        info["AssetLoanMin"] = 0
    return int(new_loan)


# ------------------------------------------------------------------
# 价格 / 涨跌停
# ------------------------------------------------------------------
def set_price_init(info, raw):
    """写入发行价 PriceInit（raw 为内部值=显示价×100）。"""
    info["PriceInit"] = raw


def set_price_fact_sync_candles(info, raw):
    """写入昨收 PriceFact，并强制同步最后一根 K 线的 OHLC（保证游戏内
    最新价/总市值立刻改变）。无 K 线则就地新建一根（Day 不自增）。"""
    info["PriceFact"] = raw
    if info.get("Candles") and len(info["Candles"]) > 0:
        last = info["Candles"][-1]
        last["Close"] = raw
        last["Open"] = raw
        if "High" in last and last["High"] < raw:
            last["High"] = raw
        if "Low" in last and last["Low"] > raw:
            last["Low"] = raw
    else:
        info["Candles"] = [{"Day": 1, "Open": raw, "Close": raw, "High": raw, "Low": raw,
                            "Volume": 0, "Amount": 0}]


def set_rate_limit(info, pct):
    """写入涨跌停幅度 RateLimit（pct 为百分数，如 10 表示 10%）。"""
    info["RateLimit"] = pct / 100


# ------------------------------------------------------------------
# 财务字段批量写入 + 万/亿 解析
# ------------------------------------------------------------------
def parse_magnitude(text, default=0):
    """把「1000000 / 100万 / 5亿」之类的中文量级文本解析为整数内部值。

    空串或无法解析时返回 default。
    """
    if text is None:
        return default
    v = str(text).strip().replace(",", "")
    if not v:
        return default
    try:
        if "万" in v:
            return int(float(v.replace("万", "")) * 10000)
        if "亿" in v:
            return int(float(v.replace("亿", "")) * 100000000)
        return int(float(v))
    except (ValueError, TypeError):
        return default


def apply_financial_fields(info, field_map):
    """批量写入财务字段，并把 Prev 同步到当前、Min 归零、重算 ProfitNetPrev。

    field_map: {字段名: 内部整数值}。只写明确给出的字段。
    """
    for k, v in field_map.items():
        info[k] = v
    # 同步历史字段 Prev = 当前
    for k in ("AssetNetPrev", "AssetLoanPrev", "RewardBusinessPrev",
              "RewardOtherPrev", "CostBusinessPrev", "CostOtherPrev"):
        base_key = k.replace("Prev", "")
        if k in info and base_key in info:
            info[k] = info[base_key]
    # Min 归零
    for k in ("AssetNetMin", "AssetLoanMin", "RewardBusinessMin",
              "RewardOtherMin", "CostBusinessMin", "CostOtherMin"):
        if k in info:
            info[k] = 0
    if "ProfitNetPrev" in info:
        info["ProfitNetPrev"] = (info.get("RewardBusiness", 0) + info.get("RewardOther", 0)
                                 - info.get("CostBusiness", 0) - info.get("CostOther", 0))


# ------------------------------------------------------------------
# NPC 挂单（主力/散户可卖股数、可买资金）
# ------------------------------------------------------------------
def clear_npc_quotes(inst, ret):
    """清零主力/散户挂单（VolSell=0, AmountBuy=0）。"""
    inst["VolumeUsableSell"] = 0
    inst["AmountUsableBuy"] = 0
    ret["VolumeUsableSell"] = 0
    ret["AmountUsableBuy"] = 0


def _median(values):
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def set_npc_quotes_by_median(e, stock, mult):
    """把某只股票的主力/散户挂单设为「其他股票中位数 × mult」。

    mult: 1.0=中位, 1.5=1.5倍, 0.5=缩量。返回写入后的 (inst_vus, ret_vus)。
    """
    code = stock["Info"]["Code"]
    aubs = [x["Institution"][0].get("AmountUsableBuy", 0) for x in e.stocks() if x["Info"]["Code"] != code]
    vuss = [x["Institution"][0].get("VolumeUsableSell", 0) for x in e.stocks() if x["Info"]["Code"] != code]
    raubs = [x["Retail"][0].get("AmountUsableBuy", 0) for x in e.stocks() if x["Info"]["Code"] != code]
    rvuss = [x["Retail"][0].get("VolumeUsableSell", 0) for x in e.stocks() if x["Info"]["Code"] != code]
    inst = stock["Institution"][0]
    ret = stock["Retail"][0]
    inst["VolumeUsableSell"] = int(_median(vuss) * mult)
    inst["AmountUsableBuy"] = int(_median(aubs) * mult)
    ret["VolumeUsableSell"] = int(_median(rvuss) * mult)
    ret["AmountUsableBuy"] = int(_median(raubs) * mult)
    return inst["VolumeUsableSell"], ret["VolumeUsableSell"]


def set_npc_quotes_custom(inst, ret, vus, aub, rvus, raub):
    """把主力/散户挂单设为用户给定的 4 个自定义值。"""
    inst["VolumeUsableSell"] = vus
    inst["AmountUsableBuy"] = aub
    ret["VolumeUsableSell"] = rvus
    ret["AmountUsableBuy"] = raub


# ------------------------------------------------------------------
# 购买取向 NoticeStyle（全局 NPC 行为预设）
# ------------------------------------------------------------------
def apply_notice_style(ns, mode):
    """按预设模式写 NoticeStyle（modes 1..5）。mode 6 由调用方自行写键。

    返回是否发生修改。ns 是 data["Market"]["NoticeStyle"]。
    """
    if mode == 1:
        ns["NormalStockStrength"] = 2.0
        ns["NormalStockCreateProb"] = 0.5
    elif mode == 2:
        ns["NormalSectorStrength"] = 1.5
    elif mode == 3:
        ns["NormalSectorStrength"] = 0.5
        ns["NormalSectorCreateProb"] = 0.0
    elif mode == 4:
        ns["NormalStockStrength"] = 0.5
        ns["NormalStockCreateProb"] = 0.0
    elif mode == 5:
        ns["NormalMarketStrength"] = 1.0
        ns["NormalMarketCreateProb"] = 0.0
        ns["NormalSectorStrength"] = 1.0
        ns["NormalSectorCreateProb"] = 0.0
        ns["NormalStockStrength"] = 1.0
        ns["NormalStockCreateProb"] = 0.0
    else:
        return False
    return True


# ------------------------------------------------------------------
# 智能增发（筹码不足时同比例扩股，维持估值）
# ------------------------------------------------------------------
def dilute_for_shortage(stock, shortage):
    """玩家买入量超过 NPC 可用筹码时触发定向增发：同比例扩大总股本/流通股，
    并等比例放大所有财务指标，维持 PE/PB 和每股数据不变。返回扩容倍数。"""
    info = stock["Info"]
    old_total = info.get("VolumeTotal", 1)
    if old_total <= 0:
        old_total = 1

    new_total = old_total + shortage
    multiplier = new_total / old_total

    info["VolumeTotal"] = int(new_total)
    info["VolumeFlow"] = info.get("VolumeFlow", 0) + shortage

    finance_keys = [
        "AssetNet", "AssetLoan",
        "RewardBusiness", "RewardOther", "CostBusiness", "CostOther",
        "AssetNetPrev", "AssetLoanPrev",
        "RewardBusinessPrev", "RewardOtherPrev", "CostBusinessPrev", "CostOtherPrev",
        "ProfitNetPrev",
    ]
    for k in finance_keys:
        if k in info:
            info[k] = int(info[k] * multiplier)
    return multiplier


# 向后兼容别名：原 TUI 用 dilute_stock_for_shortage 之名
dilute_stock_for_shortage = dilute_for_shortage


# ------------------------------------------------------------------
# 批量操作（对一组股票统一设置）
# ------------------------------------------------------------------
def batch_set_npc_quotes(e, codes, *, amount_buy=None, volume_sell=None,
                         apply_inst=True, apply_ret=True):
    """批量设置一组股票的主力/散户挂单。

    - amount_buy: 设 AmountUsableBuy（「愿意购入」资金）。None=不改。
    - volume_sell: 设 VolumeUsableSell（卖压股数）。None=不改。
    - apply_inst / apply_ret: 是否作用于主力 / 散户。
    返回 {code: {amount_buy, volume_sell}} 摘要（仅含处理过的股票）。

    语义提示：amount_buy 调高=容易涨、清零=无人买；volume_sell 调高=卖压大涨不动、清零=卖不动。
    """
    results = {}
    for code in codes:
        stock = e.find(code)
        if stock is None:
            continue
        targets = []
        if apply_inst and stock.get("Institution"):
            targets.append(stock["Institution"][0])
        if apply_ret and stock.get("Retail"):
            targets.append(stock["Retail"][0])
        for acc in targets:
            if amount_buy is not None:
                acc["AmountUsableBuy"] = amount_buy
            if volume_sell is not None:
                acc["VolumeUsableSell"] = volume_sell
        e.modified = True
        results[code] = {"amount_buy": amount_buy, "volume_sell": volume_sell}
    return results


def batch_set_notice_style(e, codes, *, strength=None, create_prob=None):
    """批量设置一组股票对应的 NPC 购买取向（NoticeStyle 的个股参数）。

    - strength: NormalStockStrength（NPC 买入个股力度，>1 增强/<1 减弱）。None=不改。
    - create_prob: NormalStockCreateProb（NPC 主动建仓个股概率 0~1）。None=不改。
    返回 {code: True} 摘要。

    注：NoticeStyle 是全局对象，本函数只写个股级参数（对所有股票生效）；
    传 codes 仅用于校验这些股票存在 + 计数。
    """
    ns = e.data["Market"].get("NoticeStyle")
    if not isinstance(ns, dict):
        ns = {}
        e.data["Market"]["NoticeStyle"] = ns
    if strength is not None:
        ns["NormalStockStrength"] = strength
    if create_prob is not None:
        ns["NormalStockCreateProb"] = create_prob
    count = sum(1 for c in codes if e.find(c) is not None)
    if strength is not None or create_prob is not None:
        e.modified = True
    return {"applied": count, "strength": strength, "create_prob": create_prob}

