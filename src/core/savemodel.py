"""SaveModel —— 存档字段的「唯一中间层」。

铁律：core 业务代码**只许**通过 model 的 getter/setter 访问字段，
不得直接读 ``model._d[...]``（仅供 model 内部 + Editor 落盘用）。
这样所有 ×100 单位换算都收口在此文件，新代码永不踩 ×100 坑。

单位约定（游戏存档）：
- 内部值 = 显示值 × 100（价格以「分」存、股数/金额 ×100 存）。
- SaveModel 内部**存内部值**（与 .sav 文件一一对应），getter 返回**显示值**（/100），
  setter 接收**显示值**、内部 ×100 存。
- 不缩放字段（Code/RateLimit 小数/Limit bool/Bourse/Sector/Day 索引/哨兵 -1）：原样。
- Candles.Volume 是「手(lots)」，**唯一例外**——不是 ×100。1 手 = 100 显示股。

哨兵：``VolumeUsableSell == -1`` 表示「无限制」。getter 会把它变成 -0.01，
故哨兵检测**必须**用 ``*_raw`` 访问器（如 ``acc.volume_usable_sell_raw``）。
"""

import json
from pathlib import Path

# 缩放常量（唯一来源）
PRICE_SCALE = 100   # 价格：显示元 ↔ 内部分
SHARE_SCALE = 100   # 股数：显示股 ↔ 内部
MONEY_SCALE = 100   # 金额：显示元 ↔ 内部


class _Scaled:
    """描述符：显示值 ↔ 内部值（按 scale），getter 返回显示、setter 收显示×scale 存内部。"""

    def __init__(self, key, scale=MONEY_SCALE):
        self._key = key
        self._scale = scale

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        return obj._d.get(self._key, 0) / self._scale

    def __set__(self, obj, value):
        obj._d[self._key] = int(round(value * self._scale))


def _scaled_pair(key, scale):
    """生成 (显示属性, raw 属性) 的一对 property，便于手写带 raw 的字段。"""
    def getter(self):
        return self._d.get(key, 0) / scale

    def setter(self, value):
        self._d[key] = int(round(value * scale))

    def getter_raw(self):
        return self._d.get(key, 0)
    return property(getter, setter), property(getter_raw)


# ------------------------------------------------------------------
# CandleModel
# ------------------------------------------------------------------
class CandleModel:
    """单根 K 线。OHLC/Amount 均 ×100；Volume 是「手(lots)」——唯一不 ×100 的量。"""

    __slots__ = ("_d",)

    def __init__(self, d):
        self._d = d

    @property
    def day(self):           # int 索引，不缩放
        return self._d.get("Day", 0)

    @day.setter
    def day(self, v):
        self._d["Day"] = v

    # OHLC：×100
    @property
    def open(self):
        return self._d.get("Open", 0) / PRICE_SCALE

    @open.setter
    def open(self, yuan):
        self._d["Open"] = int(round(yuan * PRICE_SCALE))

    @property
    def close(self):
        return self._d.get("Close", 0) / PRICE_SCALE

    @close.setter
    def close(self, yuan):
        self._d["Close"] = int(round(yuan * PRICE_SCALE))

    @property
    def high(self):
        return self._d.get("High", 0) / PRICE_SCALE

    @high.setter
    def high(self, yuan):
        self._d["High"] = int(round(yuan * PRICE_SCALE))

    @property
    def low(self):
        return self._d.get("Low", 0) / PRICE_SCALE

    @low.setter
    def low(self, yuan):
        self._d["Low"] = int(round(yuan * PRICE_SCALE))

    @property
    def amount(self):        # ×100，显示元
        return self._d.get("Amount", 0) / MONEY_SCALE

    @amount.setter
    def amount(self, yuan):
        self._d["Amount"] = int(round(yuan * MONEY_SCALE))

    @property
    def volume_lots(self):   # 「手」，原样，NOT ×100
        """K 线成交量，单位「手」(1 手 = 100 显示股)。原样返回，不缩放。"""
        return self._d.get("Volume", 0)

    @volume_lots.setter
    def volume_lots(self, lots):
        self._d["Volume"] = lots

    @property
    def volume_shares(self):
        """成交量换算成显示股 = 手 × 100。"""
        return self._d.get("Volume", 0) * 100


# ------------------------------------------------------------------
# InfoModel
# ------------------------------------------------------------------
class InfoModel:
    """单只股票的 Info dict 视图。"""

    __slots__ = ("_d",)

    def __init__(self, d):
        self._d = d

    # --- 不缩放字段 ---
    @property
    def code(self):
        return self._d.get("Code")

    @code.setter
    def code(self, v):
        self._d["Code"] = v

    @property
    def rate_limit(self):
        """涨跌停幅度，小数（如 0.10 表示 10%）——不是 ×100。"""
        return self._d.get("RateLimit", 0.10)

    @rate_limit.setter
    def rate_limit(self, frac):
        self._d["RateLimit"] = frac

    def set_rate_limit_pct(self, pct):
        """按百分数设 RateLimit（pct=10 → 0.10）。"""
        self._d["RateLimit"] = pct / 100.0

    @property
    def limit(self):
        return self._d.get("Limit", False)

    @property
    def bourse(self):
        return self._d.get("Bourse")

    @bourse.setter
    def bourse(self, v):
        self._d["Bourse"] = v

    @property
    def sector(self):
        return self._d.get("Sector")

    @sector.setter
    def sector(self, v):
        self._d["Sector"] = v

    # --- 价格（×100，显示元）+ raw ---
    price_init, price_init_raw = _scaled_pair("PriceInit", PRICE_SCALE)
    price_fact, price_fact_raw = _scaled_pair("PriceFact", PRICE_SCALE)

    # --- 股数（×100，显示股）+ raw ---
    volume_total, volume_total_raw = _scaled_pair("VolumeTotal", SHARE_SCALE)
    volume_flow, volume_flow_raw = _scaled_pair("VolumeFlow", SHARE_SCALE)
    volume_flow_init, volume_flow_init_raw = _scaled_pair("VolumeFlowInit", SHARE_SCALE)

    # --- 金额/财务（×100，显示元），用 _Scaled 描述符 ---
    asset_net = _Scaled("AssetNet")
    asset_loan = _Scaled("AssetLoan")
    reward_business = _Scaled("RewardBusiness")
    reward_other = _Scaled("RewardOther")
    cost_business = _Scaled("CostBusiness")
    cost_other = _Scaled("CostOther")
    profit_net_prev = _Scaled("ProfitNetPrev")
    net_profit_stored = _Scaled("NetProfit")
    # Prev 同步字段
    asset_net_prev = _Scaled("AssetNetPrev")
    asset_loan_prev = _Scaled("AssetLoanPrev")
    reward_business_prev = _Scaled("RewardBusinessPrev")
    reward_other_prev = _Scaled("RewardOtherPrev")
    cost_business_prev = _Scaled("CostBusinessPrev")
    cost_other_prev = _Scaled("CostOtherPrev")
    # Min 字段
    asset_net_min = _Scaled("AssetNetMin")
    asset_loan_min = _Scaled("AssetLoanMin")
    reward_business_min = _Scaled("RewardBusinessMin")
    reward_other_min = _Scaled("RewardOtherMin")
    cost_business_min = _Scaled("CostBusinessMin")
    cost_other_min = _Scaled("CostOtherMin")

    @property
    def net_profit(self):
        """派生：当前净利润（显示元）= 收益-成本，全部 ×100 后 /100。"""
        np_raw = (self._d.get("RewardBusiness", 0) + self._d.get("RewardOther", 0)
                  - self._d.get("CostBusiness", 0) - self._d.get("CostOther", 0))
        return np_raw / MONEY_SCALE

    @property
    def debt_ratio(self):
        """负债率（小数 0~1）——不缩放。"""
        loan = self._d.get("AssetLoan", 0)
        net = self._d.get("AssetNet", 0)
        total = loan + net
        return (loan / total) if total else 0.0

    @property
    def candles(self):
        return [CandleView(c) for c in self._d.get("Candles", [])]

    @property
    def last_close_raw(self):
        """「当前价」的内部值 = 最后一根 K 线 Close；无 K 线回退 PriceFact。

        真实存档里 PriceFact 是陈旧参考值（≈发行价量级，基本不动），股票真实价
        只在 K 线里，故「现价/昨收」一律取最后一根 K 线 Close（与游戏显示一致）。
        """
        cds = self._d.get("Candles") or []
        if cds:
            return cds[-1].get("Close", 0)
        return self._d.get("PriceFact", 0)

    @property
    def last_close(self):
        """「当前价」显示元 = last_close_raw / 100。"""
        return self.last_close_raw / PRICE_SCALE


# 别名（InfoModel.candles 返回 CandleView，与文件其余命名一致）
CandleView = CandleModel


# ------------------------------------------------------------------
# AccountModel / PositionModel
# ------------------------------------------------------------------
class AccountModel:
    """主力(Institution)/散户(Retail)/游资(HotMoney)/NPC 账户视图。"""

    __slots__ = ("_d",)

    def __init__(self, d):
        self._d = d

    volume_usable_sell, volume_usable_sell_raw = _scaled_pair("VolumeUsableSell", SHARE_SCALE)
    amount_usable_buy, amount_usable_buy_raw = _scaled_pair("AmountUsableBuy", MONEY_SCALE)
    init_volume_sell, init_volume_sell_raw = _scaled_pair("InitVolumeSell", SHARE_SCALE)
    init_amount_buy, init_amount_buy_raw = _scaled_pair("InitAmountBuy", MONEY_SCALE)

    @property
    def is_unlimited(self):
        """是否「无限制」可卖（VolumeUsableSell == -1）。用 raw 检测，避免浮点。"""
        return self._d.get("VolumeUsableSell", 0) == -1


class PositionModel:
    """玩家或 NPC 的单条持仓。"""

    __slots__ = ("_d",)

    def __init__(self, d):
        self._d = d

    @property
    def code(self):
        return self._d.get("Code")

    volume_usable, volume_usable_raw = _scaled_pair("VolumeUsable", SHARE_SCALE)
    amount, amount_raw = _scaled_pair("Amount", MONEY_SCALE)


# NPC 账户种类键
NPC_KEYS = ["AloneNpc", "HuddleNpc", "MessageNpc", "RelayNpc", "SneakNpc"]


# ------------------------------------------------------------------
# StockModel
# ------------------------------------------------------------------
class StockModel:
    """单只股票：Info + Institution + Retail + (可选 HotMoney)。"""

    __slots__ = ("_d",)

    def __init__(self, d):
        self._d = d

    @property
    def info(self):
        return InfoModel(self._d["Info"])

    @property
    def institution(self):
        lst = self._d.get("Institution") or []
        return AccountModel(lst[0]) if lst else AccountModel({})

    @property
    def retail(self):
        lst = self._d.get("Retail") or []
        return AccountModel(lst[0]) if lst else AccountModel({})

    @property
    def hot_money(self):
        lst = self._d.get("HotMoney") or []
        return AccountModel(lst[0]) if lst else None

    def npc_accounts(self, kind):
        """某类 NPC 账户列表（kind in NPC_KEYS）。"""
        return [AccountModel(a) for a in (self._d.get(kind) or [])]

    @property
    def sellable_chips(self):
        """主力+散户可卖筹码（显示股）。这是「市场实际可交易筹码」，
        通常远小于流通股 VolumeFlow（游戏不追踪全部流通筹码）。"""
        iv = (self._d.get("Institution") or [{}])[0].get("VolumeUsableSell", 0)
        rv = (self._d.get("Retail") or [{}])[0].get("VolumeUsableSell", 0)
        return (iv + rv) / SHARE_SCALE

    def account(self, kind):
        """按名称取账户视图：'inst'/'ret'/'hot' → AccountModel 或 None。"""
        if kind == "inst":
            return self.institution
        if kind == "ret":
            return self.retail
        if kind == "hot":
            return self.hot_money
        return None


# ------------------------------------------------------------------
# PlayerModel
# ------------------------------------------------------------------
class PlayerModel:
    """玩家：现金 + 持仓列表。"""

    __slots__ = ("_d",)

    def __init__(self, d):
        self._d = d

    amount, amount_raw = _scaled_pair("Amount", MONEY_SCALE)
    amount_init, amount_init_raw = _scaled_pair("AmountInit", MONEY_SCALE)

    @property
    def positions(self):
        return [PositionModel(p) for p in self._d.get("StockPos", [])]

    def find_position(self, code):
        for p in self._d.get("StockPos", []):
            if p.get("Code") == code:
                return PositionModel(p)
        return None

    def upsert_position(self, code):
        """返回 code 的 PositionModel；不存在则新建空持仓。"""
        for p in self._d.get("StockPos", []):
            if p.get("Code") == code:
                return PositionModel(p)
        rec = {"Code": code, "Amount": 0, "VolumeUsable": 0}
        self._d.setdefault("StockPos", []).append(rec)
        return PositionModel(rec)

    def remove_position(self, code):
        """删除 code 持仓；返回被删的 VolumeUsable_raw（未找到返回 None）。"""
        sp = self._d.get("StockPos", [])
        for p in sp:
            if p.get("Code") == code:
                old = p.get("VolumeUsable", 0)
                self._d["StockPos"] = [q for q in sp if q.get("Code") != code]
                return old
        return None

    @property
    def trade_type(self):
        return self._d.get("TradeType", [])

    @property
    def optional(self):
        return self._d.get("Optional", [])


# ------------------------------------------------------------------
# SaveModel（顶层）
# ------------------------------------------------------------------
class SaveModel:
    """完整存档。内部持原始 dict 树（内部值），与 .sav 一一对应。"""

    __slots__ = ("_d",)

    def __init__(self, d):
        self._d = d

    @classmethod
    def from_dict(cls, d):
        """从已加载的 dict 构造（load 已读完 JSON）。"""
        return cls(d)

    @classmethod
    def load(cls, path):
        """读 .sav 文件 → SaveModel。"""
        with open(path, "r", encoding="utf-8") as f:
            return cls(json.load(f))

    def dump(self):
        """返回内部 dict（用于序列化）。"""
        return self._d

    def write(self, path, compact=True):
        """把内部树写回 .sav（紧凑 JSON，ensure_ascii=False）。"""
        path = Path(path)
        if compact:
            json.dump(self._d, open(path, "w", encoding="utf-8"),
                      ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(self._d, open(path, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)

    # --- 导航 ---
    @property
    def market(self):
        return self._d.get("Market", {})

    @property
    def stocks(self):
        return [StockModel(s) for s in self._d.get("Market", {}).get("Stocks", [])]

    def find(self, code):
        """按 Code 找股票；返回 StockModel 或 None。"""
        for s in self._d.get("Market", {}).get("Stocks", []):
            if s.get("Info", {}).get("Code") == code:
                return StockModel(s)
        return None

    def codes(self):
        return sorted([s.get("Info", {}).get("Code")
                       for s in self._d.get("Market", {}).get("Stocks", [])
                       if s.get("Info", {}).get("Code") is not None])

    @property
    def player(self):
        return PlayerModel(self._d.get("Player", {}))

    @property
    def notice_style(self):
        return self._d.get("Market", {}).get("NoticeStyle", {})

    @property
    def notice_group(self):
        return self._d.get("Market", {}).get("NoticeGroup", {})

    def get_or_create_delisted_pool(self):
        """确保 DelistedPool={A:[],B:[]} 存在；返回该 dict。"""
        m = self._d.setdefault("Market", {})
        pool = m.get("DelistedPool")
        if not isinstance(pool, dict):
            m["DelistedPool"] = {"A": [], "B": []}
        pool = m["DelistedPool"]
        if not isinstance(pool.get("A"), list):
            pool["A"] = []
        if not isinstance(pool.get("B"), list):
            pool["B"] = []
        return pool

    def npc_account_list(self, kind):
        """某类 NPC 顶层账户列表（kind in NPC_KEYS）。"""
        return self._d.get("Market", {}).get(kind, []) or []

