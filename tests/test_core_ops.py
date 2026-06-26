"""src.core.stock_ops 纯函数单元测试（补充测试，不依赖 TUI harness）。

复用 tests/helpers.py 的 make_stock / make_save 构造存档片段，直接断言纯核心
函数的输入/输出，无需 mock 任何交互。
"""
import math
import unittest

from tests.helpers import make_stock, make_save, sse
from src.core import stock_ops
from src.core import player_ops


class TestSetTargetPE(unittest.TestCase):
    def _info(self):
        return make_stock(2001, price_fact=100000, volume_total=100_000_000,
                          reward_business=500_000_000, cost_business=300_000_000)["Info"]

    def test_writes_target_net_profit_and_round_trip(self):
        info = self._info()
        stock_ops.set_target_pe(info, 1.0)
        # PE=1 => NP = p*v/(100*1) = 100000 * 1e8 / 100 = 1e11
        self.assertEqual(info["RewardBusiness"], 100_000_000_000)
        self.assertEqual(info["CostBusiness"], 0)
        # 往返：改完 PE 应正好等于目标
        self.assertAlmostEqual(sse.calc_pe(info), 1.0, places=4)

    def test_prev_and_min_synced(self):
        info = self._info()
        stock_ops.set_target_pe(info, 2.0)
        self.assertEqual(info["RewardBusinessPrev"], info["RewardBusiness"])
        self.assertEqual(info["RewardBusinessMin"], 0)
        self.assertEqual(info["CostBusinessPrev"], 0)


class TestSetTargetPB(unittest.TestCase):
    def test_writes_asset_net_and_round_trip(self):
        info = make_stock(2001, price_fact=100000, volume_total=100_000_000)["Info"]
        stock_ops.set_target_pb(info, 0.5)
        # PB=0.5 => AssetNet = p*v/(100*0.5) = 100000*1e8/50 = 2e11
        self.assertEqual(info["AssetNet"], 200_000_000_000)
        self.assertEqual(info["AssetNetPrev"], info["AssetNet"])
        self.assertEqual(info["AssetNetMin"], 0)
        self.assertAlmostEqual(sse.calc_pb(info), 0.5, places=4)


class TestSetTargetDebtRatio(unittest.TestCase):
    def test_writes_asset_loan_and_round_trip(self):
        info = make_stock(2001, asset_net=1_000_000_000, asset_loan=0)["Info"]
        stock_ops.set_target_debt_ratio(info, 30.0)
        # 负债率30% => Loan = Net*30/70
        self.assertEqual(info["AssetLoan"], int(1_000_000_000 * 30 / 70))
        self.assertEqual(info["AssetLoanPrev"], info["AssetLoan"])
        self.assertEqual(info["AssetLoanMin"], 0)
        dr = info["AssetLoan"] / (info["AssetLoan"] + info["AssetNet"]) * 100
        self.assertAlmostEqual(dr, 30.0, places=2)


class TestSetPriceFactSyncCandles(unittest.TestCase):
    def test_syncs_low_on_drop(self):
        info = make_stock(2001, price_fact=100000)["Info"]
        # 默认 candle High=price+1000(=101000), Low=price-1000(=99000)；
        # 新内部价 1500(显示15) 远低于 Low，故 Low 被拉低、High 保持原值。
        stock_ops.set_price_fact_sync_candles(info, 1500)
        last = info["Candles"][-1]
        self.assertEqual(last["Close"], 1500)
        self.assertEqual(last["Open"], 1500)
        self.assertEqual(last["Low"], 1500)      # 被拉低
        self.assertEqual(last["High"], 101000)   # 原始 High 保持不变
        self.assertEqual(info["PriceFact"], 1500)

    def test_syncs_high_on_rise(self):
        info = make_stock(2001, price_fact=100000)["Info"]
        stock_ops.set_price_fact_sync_candles(info, 200000)  # 远高于 High
        last = info["Candles"][-1]
        self.assertEqual(last["High"], 200000)
        self.assertEqual(last["Low"], 100000 - 1000)  # Low 不动

    def test_creates_candle_when_empty(self):
        info = make_stock(2001, candles=[])["Info"]
        stock_ops.set_price_fact_sync_candles(info, 12345)
        self.assertEqual(len(info["Candles"]), 1)
        self.assertEqual(info["Candles"][0]["Day"], 1)
        self.assertEqual(info["Candles"][0]["Close"], 12345)


class TestSetRateLimit(unittest.TestCase):
    def test_writes_fraction(self):
        info = {"RateLimit": 0.10}
        stock_ops.set_rate_limit(info, 20)
        self.assertEqual(info["RateLimit"], 0.20)


class TestParseMagnitude(unittest.TestCase):
    def test_plain_int(self):
        self.assertEqual(stock_ops.parse_magnitude("1000000"), 1_000_000)

    def test_wan(self):
        self.assertEqual(stock_ops.parse_magnitude("100万"), 1_000_000)

    def test_yi(self):
        self.assertEqual(stock_ops.parse_magnitude("5亿"), 500_000_000)

    def test_comma_stripped(self):
        self.assertEqual(stock_ops.parse_magnitude("1,000,000"), 1_000_000)

    def test_blank_returns_default(self):
        self.assertEqual(stock_ops.parse_magnitude("", 42), 42)
        self.assertEqual(stock_ops.parse_magnitude("   ", 42), 42)

    def test_garbage_returns_default(self):
        self.assertEqual(stock_ops.parse_magnitude("abc", 7), 7)


class TestApplyFinancialFields(unittest.TestCase):
    def test_writes_and_syncs_prev_min(self):
        info = make_stock(2001)["Info"]
        stock_ops.apply_financial_fields(info, {
            "VolumeTotal": 200_000_000,
            "AssetNet": 999,
        })
        self.assertEqual(info["VolumeTotal"], 200_000_000)
        self.assertEqual(info["AssetNet"], 999)
        # Prev 同步当前
        self.assertEqual(info["AssetNetPrev"], 999)
        # Min 归零
        self.assertEqual(info["AssetNetMin"], 0)
        # ProfitNetPrev 重算
        self.assertEqual(info["ProfitNetPrev"],
                         info["RewardBusiness"] + info["RewardOther"]
                         - info["CostBusiness"] - info["CostOther"])


class TestApplyNoticeStyle(unittest.TestCase):
    def _ns(self):
        return {
            "NormalMarketStrength": 1.0, "NormalMarketCreateProb": 0.0,
            "NormalSectorStrength": 1.0, "NormalSectorCreateProb": 0.0,
            "NormalStockStrength": 1.0, "NormalStockCreateProb": 0.0,
            "RankCreateExchangeRate": 1, "ReportCreateDay": 5,
        }

    def test_mode1_push_individual_stock(self):
        ns = self._ns()
        stock_ops.apply_notice_style(ns, 1)
        self.assertEqual(ns["NormalStockStrength"], 2.0)
        self.assertEqual(ns["NormalStockCreateProb"], 0.5)

    def test_mode5_reset_all(self):
        ns = self._ns()
        ns["NormalStockStrength"] = 5.0
        stock_ops.apply_notice_style(ns, 5)
        for k in ("NormalMarketStrength", "NormalSectorStrength", "NormalStockStrength"):
            self.assertEqual(ns[k], 1.0)
        for k in ("NormalMarketCreateProb", "NormalSectorCreateProb", "NormalStockCreateProb"):
            self.assertEqual(ns[k], 0.0)

    def test_unknown_mode_no_change(self):
        ns = self._ns()
        self.assertFalse(stock_ops.apply_notice_style(ns, 6))
        self.assertEqual(ns["NormalStockStrength"], 1.0)


class TestDiluteForShortage(unittest.TestCase):
    def test_scales_proportionally_preserves_pe_pb(self):
        stock = make_stock(2001, volume_total=100_000_000, volume_flow=100_000_000,
                           asset_net=5_000_000_000, asset_loan=2_000_000_000,
                           reward_business=500_000_000)
        info = stock["Info"]
        old_pe = sse.calc_pe(info)
        old_pb = sse.calc_pb(info)
        mult = stock_ops.dilute_for_shortage(stock, 50_000_000)
        # new_total=1.5e8, old=1e8 => mult=1.5
        self.assertAlmostEqual(mult, 1.5, places=4)
        self.assertEqual(info["VolumeTotal"], 150_000_000)
        self.assertEqual(info["VolumeFlow"], 150_000_000)
        # PE/PB 因同比例放大而不变
        self.assertAlmostEqual(sse.calc_pe(info), old_pe, places=4)
        self.assertAlmostEqual(sse.calc_pb(info), old_pb, places=4)

    def test_zero_total_guarded(self):
        stock = make_stock(2001, volume_total=0)
        mult = stock_ops.dilute_for_shortage(stock, 100)
        self.assertEqual(stock["Info"]["VolumeTotal"], 101)

    def test_alias_dilute_stock_for_shortage_exists(self):
        self.assertIs(stock_ops.dilute_stock_for_shortage, stock_ops.dilute_for_shortage)


class TestNpcQuotes(unittest.TestCase):
    def test_clear(self):
        inst = {"VolumeUsableSell": 5, "AmountUsableBuy": 5}
        ret = {"VolumeUsableSell": 3, "AmountUsableBuy": 3}
        stock_ops.clear_npc_quotes(inst, ret)
        self.assertEqual(inst["VolumeUsableSell"], 0)
        self.assertEqual(ret["AmountUsableBuy"], 0)

    def test_custom(self):
        inst = {}; ret = {}
        stock_ops.set_npc_quotes_custom(inst, ret, 1, 2, 3, 4)
        self.assertEqual((inst["VolumeUsableSell"], inst["AmountUsableBuy"]), (1, 2))
        self.assertEqual((ret["VolumeUsableSell"], ret["AmountUsableBuy"]), (3, 4))


class TestPlayerOps(unittest.TestCase):
    def test_delete_player_position(self):
        from tests.helpers import fresh_editor
        data = make_save(stock_pos=[{"Code": 2001, "Amount": 0, "VolumeUsable": 1000}])
        e = fresh_editor(data)
        self.assertEqual(player_ops.delete_player_position(e, 2001), 1000)
        self.assertIsNone(player_ops.delete_player_position(e, 2001))
        self.assertEqual(e.data["Player"]["StockPos"], [])

    def test_sync_reduced(self):
        stock = make_stock(2001, volume_usable_sell=10000)
        inst = stock["Institution"][0]
        act, _ = player_ops.sync_npc_holdings(stock, delta=3000, target=inst)
        self.assertEqual(act, "reduced")
        self.assertEqual(inst["VolumeUsableSell"], 7000)

    def test_sync_diluted(self):
        stock = make_stock(2001, volume_usable_sell=1000, volume_total=10_000_000)
        inst = stock["Institution"][0]
        act, _ = player_ops.sync_npc_holdings(stock, delta=5000, target=inst)
        self.assertEqual(act, "diluted")
        self.assertEqual(inst["VolumeUsableSell"], 0)
        self.assertEqual(stock["Info"]["VolumeTotal"], 10_004_000)

    def test_sync_unlimited(self):
        stock = make_stock(2001, volume_usable_sell=-1)
        act, _ = player_ops.sync_npc_holdings(stock, delta=999, target=stock["Institution"][0])
        self.assertEqual(act, "unlimited")
        self.assertEqual(stock["Institution"][0]["VolumeUsableSell"], -1)

    def test_sync_increased(self):
        stock = make_stock(2001, volume_usable_sell=500)
        inst = stock["Institution"][0]
        act, _ = player_ops.sync_npc_holdings(stock, delta=-200, target=inst)
        self.assertEqual(act, "increased")
        self.assertEqual(inst["VolumeUsableSell"], 700)


if __name__ == "__main__":
    unittest.main()
