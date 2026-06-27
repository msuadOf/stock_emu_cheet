"""TUI 纯展示辅助（**无 I/O、无 input/print**）。

只做字符串组装，返回 str 供 frontend 打印。绝不 import frontend，绝不产生交互副作用。
依赖标准库与 src.core（calcs 的 fmt_*/calc_* 收原始 info dict）。
"""
from src.core import fmt_p, fmt_v, fmt_m, fmt_shares, calc_pe, calc_pb


def format_stock_detail(stock, code):
    """组装单只股票的完整明细文本（多行 str）。

    stock: StockModel。读内部值展示（与游戏存档口径一致）。
    """
    info = stock.info
    d = info._d
    pe = calc_pe(d)
    pb = calc_pb(d)
    np_ = d.get("RewardBusiness", 0) + d.get("RewardOther", 0) - d.get("CostBusiness", 0) - d.get("CostOther", 0)
    loan = d.get("AssetLoan", 0)
    net = d.get("AssetNet", 0)
    debt_ratio = (loan / (loan + net) * 100) if (loan + net) else 0
    pe_str = "N/A (净利润<=0)" if pe == float("inf") else str(round(pe, 4))
    pb_str = "N/A" if pb == float("inf") else str(round(pb, 4))
    lines = [
        "=" * 70,
        "  Stock X" + str(code) + " Full Details",
        "=" * 70,
        "  Code:          X" + str(info.code),
        "  PriceInit:     " + fmt_p(d.get("PriceInit", 0)) + "  (raw=" + str(d.get("PriceInit", 0)) + ")",
        "  PriceFact:     " + fmt_p(d.get("PriceFact", 0)) + "  (raw=" + str(d.get("PriceFact", 0)) + ")",
        "  RateLimit:     " + str(round(info.rate_limit * 100, 1)) + "%",
        "  VolumeTotal:   " + fmt_shares(d.get("VolumeTotal", 0)),
        "  VolumeFlow:    " + fmt_shares(d.get("VolumeFlow", 0)),
        "  AssetNet:      " + fmt_m(net),
        "  AssetLoan:     " + fmt_m(loan),
        "  NetProfit:     " + fmt_m(np_) + "  (raw=" + str(np_) + ")",
        "  PE:            " + pe_str,
        "  PB:            " + pb_str,
        "  DebtRatio:     " + str(round(debt_ratio, 2)) + "%",
        "  Institution:   VolSell=" + str(stock.institution.volume_usable_sell_raw)
            + "  AmountBuy=" + str(stock.institution.amount_usable_buy_raw),
        "  Retail:        VolSell=" + str(stock.retail.volume_usable_sell_raw)
            + "  AmountBuy=" + str(stock.retail.amount_usable_buy_raw),
        "=" * 70,
    ]
    return "\n".join(lines)
