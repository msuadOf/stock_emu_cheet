# -*- coding: utf-8 -*-
"""v2 移植功能的回归测试。

这些用例专门守护从 v2 fork 合并进来的新功能，重点是【存档×100 缩放规则】——
v2 原版在 PE/PB、增发股数、现金分红等公式里漏掉了 /100（或 /10000），
合并时已逐一修正；这里把修正后的数值钉死，防止以后回退成 100× 的错值。

约定回顾（与 test_features.TestUnitScaling 一致）：
  - 内部金额(AssetNet/RewardBusiness/Player.Amount) = 显示元 × 100
  - 内部股数(VolumeTotal/VolumeFlow/VolumeUsable*)   = 显示股 × 100
  - PriceFact(内部价) = 显示元 × 100 (即“分”)
  - PE = PriceFact*VolumeTotal/(100*NetProfit)，PB = PriceFact*VolumeTotal/(100*AssetNet)
"""
import unittest

# 复用 helpers 里已加载的 sse 模块对象（务必用同一个对象，否则 harness 的
# mock.patch("sse.input"/"sse.print") 会 patch 到另一个副本上导致测试失效）。
from tests.helpers import sse
from tests.helpers import make_stock, make_save, fresh_editor, harness


class TestPrivatePlacementScaling(unittest.TestCase):
    """定向增发：股数公式必须是 amt_y/py*100（内部×100股），不能是 amt_y/(py*100)。"""

    def _setup(self):
        # 价格 = 10 元/股 (PriceFact=1000)；近20日均价 = 10 元
        stock = make_stock(2001, price_fact=1000, price_init=1000,
                           volume_total=100_000_000, volume_flow=100_000_000)
        data = make_save([stock], player_amount=100_000_000)  # 玩家 100万 元 (内部 1e8)
        return fresh_editor(data)

    def test_shares_not_100x_off(self):
        e = self._setup()
        # 均价10元，折价0.8 → 增发价 py=8元；投入 amt_y=1_000_000 元
        # 正确股数(内部×100): 1_000_000/8*100 = 12_500_000 内部股 = 125_000 显示股
        # v2 原版错误公式 amt_y/(py*100)=1_250 会差 10000×，被守护
        with harness(["0.8", "1000000", "y"]):
            sse.private_placement_for_code(e, 2001)
        info = e.data["Market"]["Stocks"][0]["Info"]
        added = info["VolumeTotal"] - 100_000_000
        self.assertEqual(added, 12_500_000, "增发股数应为 amt_y/py*100 (内部×100股)")
        # 流通股同步
        self.assertEqual(info["VolumeFlow"], 100_000_000 + 12_500_000)
        # 玩家持仓得到同样股数
        pos = e.data["Player"]["StockPos"]
        self.assertTrue(any(p["Code"] == 2001 for p in pos))
        entry = [p for p in pos if p["Code"] == 2001][0]
        self.assertEqual(entry["VolumeUsable"], 12_500_000)

    def test_player_amount_deducted(self):
        e = self._setup()
        with harness(["0.8", "1000000", "y"]):
            sse.private_placement_for_code(e, 2001)
        # 玩家付 1_000_000 元 → 内部扣 1_000_000*100
        self.assertEqual(e.data["Player"]["Amount"], 100_000_000 - 100_000_000)


class TestStockDividendCashScaling(unittest.TestCase):
    """现金分红：每股派息 D(元/100股) 的发放额必须按 /10000 缩放。"""

    def _setup(self):
        # 1000万显示股 = 1e9 内部股；价格 10元 (PriceFact=1000)
        stock = make_stock(2001, price_fact=1000, price_init=1000,
                           volume_total=1_000_000_000, volume_flow=1_000_000_000,
                           asset_net=5_000_000_000,  # 5000万显示元 = 5e9 内部
                           asset_loan=0)
        data = make_save([stock], player_amount=0)
        return fresh_editor(data)

    def test_cash_dividend_per_holder(self):
        e = self._setup()
        # 现金分红模式(1)，D=2.0 元/100股；do_cash 末尾会发布业绩报告(star,is_buy 两问)
        with harness(["1", "2.0", "y", "3", "1"]):
            sse.stock_dividend_for_code(e, 2001)
        # 玩家初始无持仓 → 不发；这里只校验除息价跌幅正确
        # D=2 元/100股 → 每股跌 0.02 元 → PriceFact 跌 2 (分): 1000 -> 998
        info = e.data["Market"]["Stocks"][0]["Info"]
        self.assertEqual(info["PriceFact"], 998,
                         "除息价跌幅应为 D (分): v2原版用 D_int(=200)会跌过头100×")

    def test_cash_total_dividend_not_10000x(self):
        e = self._setup()
        # 给玩家一些持仓，校验总分红额缩放正确
        e.data["Player"]["StockPos"] = [{"Code": 2001, "Amount": 0, "VolumeUsable": 100_000_000}]
        # 1e8 内部股 = 100万显示股 = 1万个“100股”单位；D=2元/100股 → 玩家应得 2万元 = 2e6 内部
        with harness(["1", "2.0", "y", "3", "1"]):
            sse.stock_dividend_for_code(e, 2001)
        got = e.data["Player"]["Amount"]
        self.assertEqual(got, 2_000_000,
                         "玩家分红应=2万元(内部2e6)；v2原版 total_hand*D_int 会得2e10(大10000×)")


class TestIssueStock(unittest.TestCase):
    """发行新股票：写出的 VolumeTotal/VolumeFlow 必须是内部值(显示股×100)，
    否则与全市场其它股票不一致(PE/PB/市值都差 100×)。"""

    def test_custom_mode_stores_internal_share_units(self):
        # 自定义模式发行：流通 1000万手(=10亿显示股), 总股本默认=floats*100=10亿股(显示)
        data = make_save([make_stock(2001)], player_amount=10_000_000)
        e = fresh_editor(data)
        # issue_stock 提示序列: 来源(2=自定义) -> code -> Bourse -> Sector ->
        #   发行价 -> 流通股数(手) -> 总股本(默认) -> 名称(空) -> 确认
        inputs = ["2", "2080",                # 模式2(自定义) + 新代码
                  "1",                        # Bourse=1(沪)
                  "2",                        # Sector=2(科技=20)
                  "10.0",                     # 发行价 10元
                  "10000000",                 # 流通股数 1000万手
                  "",                         # 总股本(默认 floats*100 = 10亿股)
                  "",                         # 股票名称(空)
                  "y"]                        # 确认发行
        with harness(inputs):
            sse.issue_stock(e)
        new = [s for s in e.data["Market"]["Stocks"] if s["Info"]["Code"] == 2080]
        self.assertTrue(new, "新股票应已加入")
        info = new[0]["Info"]
        # VolumeFlow 内部值 = floats(手)*10000 = 10_000_000*10000 = 1e11
        self.assertEqual(info["VolumeFlow"], 10_000_000 * 10000,
                         "VolumeFlow 必须存内部值(显示股×100), 不能直接存手数")
        # VolumeTotal 内部值 = total_shares(股)*100 = (floats*100)*100 = floats*10000
        self.assertEqual(info["VolumeTotal"], 10_000_000 * 100 * 100)
        # 市值(显示元) = 显示价×显示股 = 10 × 10亿 = 100亿 = 1e10
        mc = sse.calc_market_cap(info)
        self.assertAlmostEqual(mc, 1e10, delta=1e8,
                               msg="发行后市值应≈100亿元(10元×10亿股)")

    def test_calc_pe_helper_is_correct(self):
        # 镜像验证 calc_pe 带 /100
        info = {"PriceFact": 1000, "VolumeTotal": 100_000_000,
                "AssetNet": 5_000_000_000, "AssetLoan": 0,
                "RewardBusiness": 200_000_000, "RewardOther": 0,
                "CostBusiness": 0, "CostOther": 0}
        self.assertAlmostEqual(sse.calc_pe(info), 5.0, places=4)


class TestStockDividendCashNoShareChange(unittest.TestCase):
    """现金分红(除息)不得改动总股本/流通股 — 这是合并时修掉的 v2 bug。"""

    def test_cash_dividend_leaves_share_count(self):
        stock = make_stock(2001, price_fact=1000, price_init=1000,
                           volume_total=1_000_000_000, volume_flow=1_000_000_000,
                           asset_net=5_000_000_000, asset_loan=0)
        data = make_save([stock], player_amount=0)
        e = fresh_editor(data)
        before_total = e.data["Market"]["Stocks"][0]["Info"]["VolumeTotal"]
        before_flow = e.data["Market"]["Stocks"][0]["Info"]["VolumeFlow"]
        # choice=1 现金, D=2.0, 确认y, 业绩报告 star=3 is_buy=1
        with harness(["1", "2.0", "y", "3", "1"]):
            sse.stock_dividend_for_code(e, 2001)
        info = e.data["Market"]["Stocks"][0]["Info"]
        self.assertEqual(info["VolumeTotal"], before_total, "现金分红不得改总股本")
        self.assertEqual(info["VolumeFlow"], before_flow, "现金分红不得改流通股")
        # 股价除息下跌: 1000 - D(2) = 998
        self.assertEqual(info["PriceFact"], 998)


class TestMarketRectification(unittest.TestCase):
    """市场整顿：调整后 sum_hold 必须 == VolumeFlow（筹码守恒）。"""

    def test_balances_to_volume_flow(self):
        # 制造筹码不平衡：VolumeFlow=1e8，但各账户合计 > 1e8
        stock = make_stock(2001, price_fact=1000, volume_total=100_000_000,
                           volume_flow=100_000_000,
                           volume_usable_sell=60_000_000,   # 机构 6000万
                           retail_vol_sell=60_000_000)       # 散户 6000万 → 合计1.2亿 > 1亿
        data = make_save([stock], player_amount=0)
        e = fresh_editor(data)
        with harness([""]):  # 整顿无需额外输入（仅 pause）
            sse.market_rectification(e)
        info = e.data["Market"]["Stocks"][0]["Info"]
        inst = e.data["Market"]["Stocks"][0]["Institution"][0]
        ret = e.data["Market"]["Stocks"][0]["Retail"][0]
        total_hold = int(inst.get("VolumeUsableSell", 0)) + int(ret.get("VolumeUsableSell", 0))
        # 差异大(2000万)走按比例缩放，缩放后合计应等于 VolumeFlow（允许1股舍入误差）
        self.assertAlmostEqual(total_hold, info["VolumeFlow"], delta=2)


if __name__ == "__main__":
    unittest.main()
