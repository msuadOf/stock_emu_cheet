"""src.core.stock_ops 纯函数单元测试（已迁移到 SaveModel）。

函数收 InfoModel/StockModel/SaveModel（getter/setter 显示值）。本测试用
InfoModel/SavaModel 包裹 helpers 造的原始 dict，断言改用 *_raw（内部值）
或显示值。calc_pe/calc_pb 仍收原始 info dict（calcs.py 未迁移），故用 info._d。
"""
import unittest

from tests.helpers import make_stock, make_save, sse
from src.core import stock_ops
from src.core import player_ops
from src.core.savemodel import InfoModel, StockModel, SaveModel, AccountModel


class TestSetTargetPE(unittest.TestCase):
    def _info(self):
        return InfoModel(make_stock(2001, price_fact=100000, volume_total=100_000_000,
                                    reward_business=500_000_000, cost_business=300_000_000)["Info"])

    def test_writes_target_net_profit_and_round_trip(self):
        info = self._info()
        stock_ops.set_target_pe(info, 1.0)
        # PE=1 => NP(显示) = price_fact(显示1000) * volume_total(显示1e6) / 1 = 1e9 显示元
        self.assertEqual(info.reward_business, 1_000_000_000)
        self.assertEqual(info.cost_business, 0)
        self.assertAlmostEqual(sse.calc_pe(info._d), 1.0, places=4)

    def test_prev_and_min_synced(self):
        info = self._info()
        stock_ops.set_target_pe(info, 2.0)
        self.assertEqual(info._d["RewardBusinessPrev"], info._d["RewardBusiness"])
        self.assertEqual(info._d["RewardBusinessMin"], 0)
        self.assertEqual(info._d["CostBusinessPrev"], 0)


class TestSetTargetPB(unittest.TestCase):
    def test_writes_asset_net_and_round_trip(self):
        info = InfoModel(make_stock(2001, price_fact=100000, volume_total=100_000_000)["Info"])
        stock_ops.set_target_pb(info, 0.5)
        # PB=0.5 => AssetNet(显示) = 1000 * 1e6 / 0.5 = 2e9 显示元
        self.assertEqual(info.asset_net, 2_000_000_000)
        self.assertEqual(info._d["AssetNetPrev"], info._d["AssetNet"])
        self.assertEqual(info._d["AssetNetMin"], 0)
        self.assertAlmostEqual(sse.calc_pb(info._d), 0.5, places=4)


class TestSetTargetDebtRatio(unittest.TestCase):
    def test_writes_asset_loan_and_round_trip(self):
        info = InfoModel(make_stock(2001, asset_net=1_000_000_000, asset_loan=0)["Info"])
        stock_ops.set_target_debt_ratio(info, 30.0)
        # asset_net 内部 1e9 → 显示 1e7 元；负债率30% => Loan(显示) = 1e7 * 30/70
        self.assertAlmostEqual(info.asset_loan, 10_000_000 * 30 / 70, places=0)
        self.assertEqual(info._d["AssetLoanPrev"], info._d["AssetLoan"])
        self.assertEqual(info._d["AssetLoanMin"], 0)
        dr = info.debt_ratio * 100
        self.assertAlmostEqual(dr, 30.0, places=2)


class TestSetPriceFactSyncCandles(unittest.TestCase):
    def test_syncs_low_on_drop(self):
        info = InfoModel(make_stock(2001, price_fact=100000)["Info"])
        # 默认 candle High=price+1000(=101000), Low=price-1000(=99000)
        # 新内部价 1500(显示15) 远低于 Low，故 Low 被拉低、High 保持原值。
        stock_ops.set_price_fact_sync_candles(info, 15.0)
        last = info._d["Candles"][-1]
        self.assertEqual(last["Close"], 1500)
        self.assertEqual(last["Open"], 1500)
        self.assertEqual(last["Low"], 1500)
        self.assertEqual(last["High"], 101000)
        self.assertEqual(info.price_fact_raw, 1500)

    def test_syncs_high_on_rise(self):
        info = InfoModel(make_stock(2001, price_fact=100000)["Info"])
        stock_ops.set_price_fact_sync_candles(info, 2000.0)  # raw=200000 远高于 High
        last = info._d["Candles"][-1]
        self.assertEqual(last["High"], 200000)
        self.assertEqual(last["Low"], 99000)

    def test_creates_candle_when_empty(self):
        info = InfoModel(make_stock(2001, candles=[])["Info"])
        stock_ops.set_price_fact_sync_candles(info, 123.45)
        self.assertEqual(len(info._d["Candles"]), 1)
        self.assertEqual(info._d["Candles"][0]["Day"], 1)
        self.assertEqual(info._d["Candles"][0]["Close"], 12345)


class TestSetRateLimit(unittest.TestCase):
    def test_writes_fraction(self):
        info = InfoModel({"RateLimit": 0.10})
        stock_ops.set_rate_limit(info, 20)
        self.assertAlmostEqual(info.rate_limit, 0.20)


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

    def test_garbage_returns_default(self):
        self.assertEqual(stock_ops.parse_magnitude("abc", 7), 7)


class TestApplyFinancialFields(unittest.TestCase):
    def test_writes_and_syncs_prev_min(self):
        info = InfoModel(make_stock(2001)["Info"])
        stock_ops.apply_financial_fields(info, {"VolumeTotal": 200_000_000, "AssetNet": 999})
        self.assertEqual(info.volume_total, 200_000_000)
        self.assertEqual(info.asset_net, 999)
        self.assertEqual(info._d["AssetNetPrev"], info._d["AssetNet"])
        self.assertEqual(info._d["AssetNetMin"], 0)
        self.assertEqual(info._d["ProfitNetPrev"],
                         info._d["RewardBusiness"] + info._d["RewardOther"]
                         - info._d["CostBusiness"] - info._d["CostOther"])


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

    def test_unknown_mode_no_change(self):
        ns = self._ns()
        self.assertFalse(stock_ops.apply_notice_style(ns, 6))
        self.assertEqual(ns["NormalStockStrength"], 1.0)


class TestDiluteForShortage(unittest.TestCase):
    def test_scales_proportionally_preserves_pe_pb(self):
        stock = StockModel(make_stock(2001, volume_total=100_000_000, volume_flow=100_000_000,
                                      asset_net=5_000_000_000, asset_loan=2_000_000_000,
                                      reward_business=500_000_000))
        info = stock.info
        old_pe = sse.calc_pe(info._d)
        old_pb = sse.calc_pb(info._d)
        # shortage 显示股 5000万 → 内部 5e9；old_total 内部 1e8 → 多了？这里 shortage 比例大
        mult = stock_ops.dilute_for_shortage(stock, 50_000_000)
        # 显示 shortage 5e7 → 内部 5e9；old_total 内部 1e8；new=5.1e9；mult=51
        self.assertAlmostEqual(mult, 51.0, places=4)
        self.assertAlmostEqual(sse.calc_pe(info._d), old_pe, places=4)
        self.assertAlmostEqual(sse.calc_pb(info._d), old_pb, places=4)

    def test_zero_total_guarded(self):
        stock = StockModel(make_stock(2001, volume_total=0))
        mult = stock_ops.dilute_for_shortage(stock, 100)
        # old_total_raw 0 → 兜底 1；shortage 显示100→内部1e4；new=1+1e4=10001；mult=10001
        self.assertEqual(mult, 10001.0)

    def test_alias_dilute_stock_for_shortage_exists(self):
        self.assertIs(stock_ops.dilute_stock_for_shortage, stock_ops.dilute_for_shortage)


class TestNpcQuotes(unittest.TestCase):
    def test_clear(self):
        inst = AccountModel({"VolumeUsableSell": 5, "AmountUsableBuy": 5})
        ret = AccountModel({"VolumeUsableSell": 3, "AmountUsableBuy": 3})
        stock_ops.clear_npc_quotes(inst, ret)
        self.assertEqual(inst.volume_usable_sell_raw, 0)
        self.assertEqual(ret.amount_usable_buy_raw, 0)

    def test_custom(self):
        inst = AccountModel({}); ret = AccountModel({})
        stock_ops.set_npc_quotes_custom(inst, ret, 1, 2, 3, 4)
        self.assertEqual((inst.volume_usable_sell, inst.amount_usable_buy), (1, 2))
        self.assertEqual((ret.volume_usable_sell, ret.amount_usable_buy), (3, 4))


class TestPlayerOps(unittest.TestCase):
    def test_delete_player_position(self):
        data = make_save(stock_pos=[{"Code": 2001, "Amount": 0, "VolumeUsable": 1000}])
        save = SaveModel.from_dict(data)
        # remove_position 返回内部 VolumeUsable
        self.assertEqual(save.player.remove_position(2001), 1000)
        self.assertIsNone(save.player.remove_position(2001))

    def test_sync_reduced(self):
        # volume_usable_sell=10000 内部 → 显示 100；delta=50 显示 < 100 → 普通扣减
        stock = StockModel(make_stock(2001, volume_usable_sell=10000))
        inst = stock.institution
        act, _ = player_ops.sync_npc_holdings(stock, delta=50, target=inst)
        self.assertEqual(act, "reduced")
        self.assertEqual(inst.volume_usable_sell_raw, 5000)   # (100-50)显示 ×100

    def test_sync_diluted(self):
        # volume_usable_sell=1000 内部 → 显示 10；delta=5000 显示远超 → 增发
        stock = StockModel(make_stock(2001, volume_usable_sell=1000, volume_total=10_000_000))
        inst = stock.institution
        act, _ = player_ops.sync_npc_holdings(stock, delta=5000, target=inst)
        self.assertEqual(act, "diluted")
        self.assertEqual(inst.volume_usable_sell_raw, 0)

    def test_sync_unlimited(self):
        stock = StockModel(make_stock(2001, volume_usable_sell=-1))
        act, _ = player_ops.sync_npc_holdings(stock, delta=999, target=stock.institution)
        self.assertEqual(act, "unlimited")
        self.assertEqual(stock.institution.volume_usable_sell_raw, -1)

    def test_sync_increased(self):
        # volume_usable_sell=500 内部 → 显示 5；delta=-200 显示 → 新值 205 显示 → raw 20500
        stock = StockModel(make_stock(2001, volume_usable_sell=500))
        inst = stock.institution
        act, _ = player_ops.sync_npc_holdings(stock, delta=-200, target=inst)
        self.assertEqual(act, "increased")
        self.assertEqual(inst.volume_usable_sell_raw, 20500)


if __name__ == "__main__":
    unittest.main()
