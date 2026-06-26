"""纯计算 / 格式化函数：PE/PB/市值与金额/股数显示。

游戏存档约定：内部值 = 显示值 × 100
（价格以「分」存、股数/金额 ×100 存）。这些公式已内置对应的 /100 修正。
无 I/O、无副作用、无依赖。
"""


def fmt_p(r):
    """格式化【价格】（内部值/100=显示价）-> 'X.XX Yuan'。"""
    return (str(round(r / 100, 2)) + " Yuan") if r else "0 Yuan"


def fmt_v(r):
    """格式化原始数值（直接转字符串）。"""
    return str(r)


def fmt_m(r):
    """格式化【金额】字段(AssetNet/RewardBusiness 等)。

    游戏内部金额是显示元的 100 倍（即以「分」为单位存储），
    所以这里直接按原值换算万/亿就是游戏里看到的元数。
    """
    a = abs(r)
    if a >= 5e7:  # > 5000万
        formatted = f"{r:,}"
        yi = r / 1e8
        return f"{formatted} ({yi:.2f} 亿)"
    elif a >= 1e4:  # > 1万
        formatted = f"{r:,}"
        wan = r / 1e4
        return f"{formatted} ({wan:.2f} 万)"
    else:
        return str(r)


def fmt_shares(r):
    """格式化【股数】字段(VolumeTotal/VolumeFlow/VolumeUsable*)。

    游戏内部股数是显示股数的 100 倍（与价格的 ×100 规则一致），
    显示时要先 /100。返回「内部值 ｜ 显示X万/X亿股」。
    """
    disp = r / 100
    raw = f"{r:,}"
    a = abs(disp)
    if a >= 5e7:
        return f"{raw}  ｜ 显示 {disp:,.0f} ({disp/1e8:.2f} 亿) 股"
    elif a >= 1e4:
        return f"{raw}  ｜ 显示 {disp:,.0f} ({disp/1e4:.2f} 万) 股"
    else:
        return f"{raw}  ｜ 显示 {disp:,.0f} 股"


def calc_pe(info):
    """市盈率 PE = 显示价 * 显示股本 / 显示净利润。

    内部值都是显示值的 100 倍（价格以分、股数/金额以 100 为基本单位存储），
    所以分子多出的 100×100 与分母的 100 抵消，但要再除以一个 100::

        PE = (PriceFact/100) * (VolumeTotal/100) / (NetProfit/100)
           = PriceFact * VolumeTotal / (100 * NetProfit)
    """
    np_ = info["RewardBusiness"] + info["RewardOther"] - info["CostBusiness"] - info["CostOther"]
    if not np_:
        return float("inf")
    return info["PriceFact"] * info["VolumeTotal"] / (100 * np_)


def calc_pb(info):
    """市净率 PB = 显示价 * 显示股本 / 显示净资产 = PriceFact*VolumeTotal/(100*AssetNet)。"""
    if not info["AssetNet"]:
        return float("inf")
    return info["PriceFact"] * info["VolumeTotal"] / (100 * info["AssetNet"])


def calc_market_cap(info):
    """总市值(显示元) = 显示价 * 显示股本 = (PriceFact/100)*(VolumeTotal/100) = PriceFact*VolumeTotal/10000。"""
    return info["PriceFact"] * info["VolumeTotal"] / 10000
