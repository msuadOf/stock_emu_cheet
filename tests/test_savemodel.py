"""SaveModel 单元测试：getter/setter 单位矫正、哨兵、Candle lots、load/write 往返。"""
import json
import tempfile
import unittest
from pathlib import Path

from src.core.savemodel import (
    SaveModel, StockModel, InfoModel, CandleModel, AccountModel, PositionModel, PlayerModel,
)


class TestScaledRoundTrip(unittest.TestCase):
    def test_price_getter_setter(self):
        info = InfoModel({})
        info.price_fact = 12.34
        self.assertEqual(info._d["PriceFact"], 1234)        # 内部 ×100
        self.assertAlmostEqual(info.price_fact, 12.34)      # getter /100
        self.assertEqual(info.price_fact_raw, 1234)

    def test_shares_getter_setter(self):
        info = InfoModel({})
        info.volume_flow = 1_000_000   # 显示股
        self.assertEqual(info._d["VolumeFlow"], 100_000_000)
        self.assertEqual(info.volume_flow, 1_000_000)
        self.assertEqual(info.volume_flow_raw, 100_000_000)

    def test_money_descriptor(self):
        info = InfoModel({})
        info.asset_net = 5_000_000  # 显示元
        self.assertEqual(info._d["AssetNet"], 500_000_000)
        self.assertEqual(info.asset_net, 5_000_000)

    def test_rate_limit_not_scaled(self):
        info = InfoModel({"RateLimit": 0.10})
        self.assertAlmostEqual(info.rate_limit, 0.10)        # 不 /100
        info.rate_limit = 0.20
        self.assertEqual(info._d["RateLimit"], 0.20)
        info.set_rate_limit_pct(20)
        self.assertAlmostEqual(info._d["RateLimit"], 0.20)

    def test_code_not_scaled(self):
        info = InfoModel({"Code": 2075})
        self.assertEqual(info.code, 2075)

    def test_net_profit_derived(self):
        info = InfoModel({"RewardBusiness": 500_000_000, "RewardOther": 0,
                          "CostBusiness": 300_000_000, "CostOther": 0})
        self.assertEqual(info.net_profit, 2_000_000)         # (500M-300M)/100 = 2M 显示元

    def test_debt_ratio(self):
        info = InfoModel({"AssetNet": 700, "AssetLoan": 300})
        self.assertAlmostEqual(info.debt_ratio, 0.30)


class TestSentinel(unittest.TestCase):
    def test_unlimited_account(self):
        acc = AccountModel({"VolumeUsableSell": -1, "AmountUsableBuy": 1000})
        self.assertTrue(acc.is_unlimited)                    # 用 raw 检测
        self.assertEqual(acc.volume_usable_sell_raw, -1)
        # getter 会把 -1/100，故哨兵必须用 raw（这是关键陷阱）
        self.assertAlmostEqual(acc.volume_usable_sell, -0.01)


class TestCandleLots(unittest.TestCase):
    def test_ohlc_scaled_volume_not(self):
        c = CandleModel({"Day": 5, "Open": 100000, "Close": 100000,
                         "High": 101000, "Low": 99000, "Volume": 7, "Amount": 700000})
        self.assertEqual(c.day, 5)                           # 不缩放
        self.assertAlmostEqual(c.open, 1000.0)               # 价格 /100
        self.assertAlmostEqual(c.close, 1000.0)
        self.assertEqual(c.volume_lots, 7)                   # 手，原样 NOT /100
        self.assertEqual(c.volume_shares, 700)               # ×100 成显示股

    def test_candle_volume_setter_keeps_lots(self):
        c = CandleModel({})
        c.volume_lots = 12
        self.assertEqual(c._d["Volume"], 12)                 # 不被 ×100


class TestStockAndPlayer(unittest.TestCase):
    def _stock(self):
        return StockModel({
            "Info": {"Code": 2001, "PriceFact": 100000, "VolumeFlow": 100_000_000,
                     "VolumeTotal": 100_000_000},
            "Institution": [{"VolumeUsableSell": 20_000_000, "AmountUsableBuy": 10_000_000}],
            "Retail": [{"VolumeUsableSell": 10_000_000, "AmountUsableBuy": 5_000_000}],
        })

    def test_stock_nav(self):
        s = self._stock()
        self.assertEqual(s.info.code, 2001)
        self.assertAlmostEqual(s.info.price_fact, 1000.0)
        self.assertEqual(s.institution.volume_usable_sell, 200_000)   # /100
        self.assertEqual(s.retail.volume_usable_sell, 100_000)

    def test_sellable_chips(self):
        s = self._stock()
        # 主力 2000万 + 散户 1000万 内部 → /100 = 30万 显示股
        self.assertEqual(s.sellable_chips, 300_000)

    def test_player_upsert_and_amount(self):
        p = PlayerModel({"Amount": 1_000_000})
        self.assertEqual(p.amount, 10_000)                   # /100 显示元
        p.amount = 99
        self.assertEqual(p._d["Amount"], 9900)
        pos = p.upsert_position(2001)                        # 新建
        self.assertEqual(pos.code, 2001)
        pos.volume_usable = 500                              # 显示股
        self.assertEqual(pos._d["VolumeUsable"], 50_000)     # 内部 ×100
        found = p.find_position(2001)                        # 存在
        self.assertIsNotNone(found)
        self.assertEqual(found.volume_usable, 500)
        removed = p.remove_position(2001)
        self.assertEqual(removed, 50_000)
        self.assertIsNone(p.find_position(2001))


class TestSaveModelIO(unittest.TestCase):
    def test_load_write_roundtrip(self):
        data = {"Market": {"Stocks": [{"Info": {"Code": 1, "PriceFact": 1000}}]}, "Player": {"Amount": 0}}
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "t.sav"
            p.write_text(json.dumps(data), encoding="utf-8")
            m = SaveModel.load(p)
            self.assertEqual(m.find(1).info.price_fact_raw, 1000)
            m.find(1).info.price_fact = 50.0                 # 改显示值 → 内部 5000
            m.write(p)
            on_disk = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(on_disk["Market"]["Stocks"][0]["Info"]["PriceFact"], 5000)

    def test_find_returns_none(self):
        m = SaveModel.from_dict({"Market": {"Stocks": []}, "Player": {}})
        self.assertIsNone(m.find(9999))

    def test_delisted_pool(self):
        m = SaveModel.from_dict({"Market": {}, "Player": {}})
        pool = m.get_or_create_delisted_pool()
        self.assertEqual(pool, {"A": [], "B": []})


if __name__ == "__main__":
    unittest.main()
