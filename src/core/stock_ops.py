"""单只股票的主干编辑操作（纯函数，无 I/O、无交互）。

这些是把原 TUI 的 ``change_*`` 函数里「计算 + 改数据」的部分剥离出来的纯核心，
供 CLI / GUI / TUI 共享。TUI 的 wrapper 负责收输入/打印/确认，再调这里的函数。

**已迁移到 SaveModel**：函数收 ``InfoModel``/``StockModel``，全程用 getter/setter
（显示值）。×100 换算由 model 在边界处理，业务代码不再手写 /100 或 ×100。
"""
from .savemodel import InfoModel, StockModel
from .editor import codes_by_sector


# ------------------------------------------------------------------
# 估值：PE / PB / 负债率
# ------------------------------------------------------------------
def set_target_pe(info, target):
    """按目标 PE 反推净利润并写入（同时清零成本、同步 Prev/Min）。

    info: InfoModel。target: 目标 PE（显示值无量纲）。
    PE = 现价 * 显示股本 / 显示净利润  =>  NetProfit = last_close * volume_total / target
    （现价取最后 K 线 Close，与 calc_pe 同源；PriceFact 是陈旧参考值，不用。）
    返回写入的净利润（显示元）。
    """
    target_np = info.last_close * info.volume_total / target
    info.reward_business = target_np
    info.reward_other = 0
    info.cost_business = 0
    info.cost_other = 0
    info.profit_net_prev = target_np
    # Prev 同步：Reward 类=target_np，Cost 类=0（仅当 key 已存在）
    d = info._d
    for k in ("RewardBusinessPrev", "RewardOtherPrev", "CostBusinessPrev", "CostOtherPrev"):
        if k in d:
            d[k] = int(round(target_np * 100)) if "Reward" in k else 0
    for k in ("RewardBusinessMin", "RewardOtherMin", "CostBusinessMin", "CostOtherMin"):
        if k in d:
            d[k] = 0
    return target_np


def set_target_pb(info, target):
    """按目标 PB 反推净资产并写入（同步 Prev，Min 归零）。返回新净资产（显示元）。

    PB = 现价 * 显示股本 / 显示净资产 => AssetNet = last_close * volume_total / target
    （现价取最后 K 线 Close，与 calc_pb 同源。）
    """
    target_an = info.last_close * info.volume_total / target
    info.asset_net = target_an
    if "AssetNetPrev" in info._d:
        info.asset_net_prev = target_an
    if "AssetNetMin" in info._d:
        info.asset_net_min = 0
    return target_an


def set_target_debt_ratio(info, target_pct):
    """按目标负债率(百分数)反推 AssetLoan 并写入。返回新 AssetLoan（显示元）。

    负债率 = AssetLoan / (AssetLoan + AssetNet) * 100%
        =>  AssetLoan = AssetNet * target / (100 - target)
    """
    new_loan = info.asset_net * target_pct / (100 - target_pct)
    info.asset_loan = new_loan
    if "AssetLoanPrev" in info._d:
        info.asset_loan_prev = new_loan
    if "AssetLoanMin" in info._d:
        info.asset_loan_min = 0
    return new_loan


# ------------------------------------------------------------------
# 价格 / 涨跌停
# ------------------------------------------------------------------
def set_price_init(info, yuan):
    """写入发行价 PriceInit。info: InfoModel，yuan: 显示价（元）。"""
    info.price_init = yuan


def set_price_fact_sync_candles(info, yuan):
    """写入昨收 PriceFact（显示元），并强制同步最后一根 K 线的 OHLC（保证游戏内
    最新价/总市值立刻改变）。无 K 线则就地新建一根（Day 不自增）。"""
    info.price_fact = yuan
    candles = info._d.get("Candles")
    raw = info.price_fact_raw
    if candles and len(candles) > 0:
        last = candles[-1]
        last["Close"] = raw
        last["Open"] = raw
        if "High" in last and last["High"] < raw:
            last["High"] = raw
        if "Low" in last and last["Low"] > raw:
            last["Low"] = raw
    else:
        info._d["Candles"] = [{"Day": 1, "Open": raw, "Close": raw, "High": raw, "Low": raw,
                               "Volume": 0, "Amount": 0}]


def set_rate_limit(info, pct):
    """写入涨跌停幅度 RateLimit。info: InfoModel，pct: 百分数（如 10 表示 10%）。"""
    info.set_rate_limit_pct(pct)


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

    info: InfoModel。field_map: {字段名: 显示值}（如 {"AssetNet": 5000000} = 显示 500万元）。
    只写明确给出的字段。
    """
    # 字段名 → InfoModel 上的 setter 属性
    setter_map = {
        "VolumeTotal": "volume_total", "VolumeFlow": "volume_flow",
        "AssetNet": "asset_net", "AssetLoan": "asset_loan",
        "RewardBusiness": "reward_business", "RewardOther": "reward_other",
        "CostBusiness": "cost_business", "CostOther": "cost_other",
    }
    for k, v in field_map.items():
        if k in setter_map:
            setattr(info, setter_map[k], v)
        elif k in info._d:                       # 其它键按内部值原样写
            info._d[k] = v
    # 同步历史字段 Prev = 当前（Prev 也是 ×100，用 setter 保持单位一致）
    prev_map = {"AssetNetPrev": "asset_net_prev", "AssetLoanPrev": "asset_loan_prev",
                "RewardBusinessPrev": "reward_business_prev", "RewardOtherPrev": "reward_other_prev",
                "CostBusinessPrev": "cost_business_prev", "CostOtherPrev": "cost_other_prev"}
    base_attr = {"AssetNetPrev": "asset_net", "AssetLoanPrev": "asset_loan",
                 "RewardBusinessPrev": "reward_business", "RewardOtherPrev": "reward_other",
                 "CostBusinessPrev": "cost_business", "CostOtherPrev": "cost_other"}
    for k, attr in prev_map.items():
        if k in info._d:
            setattr(info, attr, getattr(info, base_attr[k]))
    # Min 归零（内部值 0）
    for k in ("AssetNetMin", "AssetLoanMin", "RewardBusinessMin",
              "RewardOtherMin", "CostBusinessMin", "CostOtherMin"):
        if k in info._d:
            info._d[k] = 0
    if "ProfitNetPrev" in info._d:
        info.profit_net_prev = info.net_profit


# ------------------------------------------------------------------
# NPC 挂单（主力/散户可卖股数、可买资金）
# ------------------------------------------------------------------
def clear_npc_quotes(inst, ret):
    """清零主力/散户挂单（VolSell=0, AmountBuy=0）。inst/ret: AccountModel。"""
    inst.volume_usable_sell = 0
    inst.amount_usable_buy = 0
    ret.volume_usable_sell = 0
    ret.amount_usable_buy = 0


def _median(values):
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def set_npc_quotes_by_median(save, stock, mult):
    """把某只股票的主力/散户挂单设为「其他股票中位数 × mult」。

    save: SaveModel，stock: StockModel。mult: 1.0=中位, 1.5=1.5倍, 0.5=缩量。
    返回写入后的 (inst_vus, ret_vus) 显示股。
    """
    code = stock.info.code
    others = [s for s in save.stocks if s.info.code != code]
    aubs = [x.institution.amount_usable_buy for x in others]
    vuss = [x.institution.volume_usable_sell for x in others]
    raubs = [x.retail.amount_usable_buy for x in others]
    rvuss = [x.retail.volume_usable_sell for x in others]
    inst, ret = stock.institution, stock.retail
    inst.volume_usable_sell = _median(vuss) * mult
    inst.amount_usable_buy = _median(aubs) * mult
    ret.volume_usable_sell = _median(rvuss) * mult
    ret.amount_usable_buy = _median(raubs) * mult
    return inst.volume_usable_sell, ret.volume_usable_sell


def set_npc_quotes_custom(inst, ret, vus, aub, rvus, raub):
    """把主力/散户挂单设为用户给定的 4 个自定义值（显示股/显示元）。inst/ret: AccountModel。"""
    inst.volume_usable_sell = vus
    inst.amount_usable_buy = aub
    ret.volume_usable_sell = rvus
    ret.amount_usable_buy = raub


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
    并等比例放大所有财务指标，维持 PE/PB 和每股数据不变。返回扩容倍数。

    stock: StockModel。shortage: 缺口（显示股）。全程显示单位，×100 由 setter 处理。
    """
    info = stock.info
    old_total = info.volume_total_raw
    if old_total <= 0:
        old_total = 1
    # shortage 是显示股，转内部参与运算（与内部 total 同单位）
    shortage_raw = int(round(shortage * 100))
    new_total = old_total + shortage_raw
    multiplier = new_total / old_total

    info._d["VolumeTotal"] = int(new_total)
    info._d["VolumeFlow"] = info.volume_flow_raw + shortage_raw

    finance_keys = [
        "AssetNet", "AssetLoan",
        "RewardBusiness", "RewardOther", "CostBusiness", "CostOther",
        "AssetNetPrev", "AssetLoanPrev",
        "RewardBusinessPrev", "RewardOtherPrev", "CostBusinessPrev", "CostOtherPrev",
        "ProfitNetPrev",
    ]
    for k in finance_keys:
        if k in info._d:
            info._d[k] = int(info._d[k] * multiplier)
    return multiplier


# 向后兼容别名：原 TUI 用 dilute_stock_for_shortage 之名
dilute_stock_for_shortage = dilute_for_shortage


# ------------------------------------------------------------------
# 批量操作（对一组股票统一设置）
# ------------------------------------------------------------------
def _resolve_codes(save, codes, sector):
    """sector 给定时取该板块全部 code（忽略 codes）；否则用 codes。"""
    if sector is not None:
        return codes_by_sector(save._d, sector)
    return codes or []


def batch_set_npc_quotes(save, codes=None, *, amount_buy=None, volume_sell=None,
                         apply_inst=True, apply_ret=True, sector=None):
    """批量设置一组股票的主力/散户挂单。

    save: SaveModel。amount_buy(显示元)/volume_sell(显示股): None=不改。
    apply_inst/apply_ret: 是否作用于主力/散户。
    sector: 给定时只作用于该板块(Sector)的所有股票（忽略 codes）。
    返回 {code: {amount_buy, volume_sell}} 摘要。

    语义提示：amount_buy 调高=容易涨、清零=无人买；volume_sell 调高=卖压大涨不动、清零=卖不动。
    """
    codes = _resolve_codes(save, codes, sector)
    results = {}
    for code in codes:
        stock = save.find(code)
        if stock is None:
            continue
        targets = []
        if apply_inst:
            targets.append(stock.institution)
        if apply_ret:
            targets.append(stock.retail)
        for acc in targets:
            if amount_buy is not None:
                acc.amount_usable_buy = amount_buy
            if volume_sell is not None:
                acc.volume_usable_sell = volume_sell
        results[code] = {"amount_buy": amount_buy, "volume_sell": volume_sell}
    return results


def batch_set_notice_style(save, codes=None, *, strength=None, create_prob=None, sector=None):
    """批量设置一组股票对应的 NPC 购买取向（NoticeStyle 的个股参数）。

    save: SaveModel。strength/create_prob: None=不改。
    sector: 给定时按板块校验计数（NoticeStyle 本身全局生效）。
    注：NoticeStyle 是全局对象，本函数只写个股级参数（对所有股票生效）；
    传 codes/sector 仅用于校验这些股票存在 + 计数。
    """
    codes = _resolve_codes(save, codes, sector)
    ns = save.notice_style
    if not isinstance(ns, dict):
        ns = {}
        save._d.setdefault("Market", {})["NoticeStyle"] = ns
    if strength is not None:
        ns["NormalStockStrength"] = strength
    if create_prob is not None:
        ns["NormalStockCreateProb"] = create_prob
    count = sum(1 for c in codes if save.find(c) is not None)
    return {"applied": count, "strength": strength, "create_prob": create_prob}

