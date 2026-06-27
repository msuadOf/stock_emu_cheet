"""src.core 批量操作函数的单元测试。

batch_set_player_pct / batch_set_npc_quotes / batch_set_notice_style。
"""
import unittest

from tests.helpers import make_stock, make_save, fresh_editor
from src.core import (
    batch_set_player_pct, batch_set_npc_quotes, batch_set_notice_style,
)


class _Ctx:
    """轻量 Editor 替身。"""
    def __init__(self, data):
        self.data = data
        self.modified = False

    def find(self, code):
        for s in self.data["Market"]["Stocks"]:
            if s["Info"]["Code"] == code:
                return s
        return None

    def stocks(self):
        return self.data["Market"]["Stocks"]


class TestBatchPlayerPct(unittest.TestCase):
    def test_sets_position_to_flow_pct(self):
        stock = make_stock(2001, volume_flow=100_000_000, volume_total=100_000_000,
                           volume_usable_sell=500_000_000)  # 主力可卖充足，不触发增发
        e = _Ctx(make_save([stock]))
        r = batch_set_player_pct(e, [2001], 10, target_account="inst")
        self.assertIn(2001, r)
        # 流通股 1e8 的 10% = 1e7
        self.assertEqual(r[2001]["volume"], 10_000_000)
        pos = e.data["Player"]["StockPos"]
        self.assertEqual(pos[0]["VolumeUsable"], 10_000_000)
        self.assertTrue(e.modified)

    def test_nonexistent_code_skipped(self):
        e = _Ctx(make_save([make_stock(2001)]))
        r = batch_set_player_pct(e, [9999], 10)
        self.assertEqual(r, {})

    def test_multiple_codes(self):
        stocks = [make_stock(c, volume_flow=100_000_000, volume_usable_sell=500_000_000)
                  for c in (2001, 2002, 2003)]
        e = _Ctx(make_save(stocks))
        r = batch_set_player_pct(e, [2001, 2002, 2003], 50, target_account="inst")
        self.assertEqual(set(r.keys()), {2001, 2002, 2003})
        for info in r.values():
            self.assertEqual(info["volume"], 50_000_000)

    def test_dilution_when_shortage(self):
        # 主力可卖不足 → 触发增发（action=diluted）
        stock = make_stock(2001, volume_flow=10_000_000, volume_total=10_000_000,
                           volume_usable_sell=1000)  # 主力只有 1000，要持仓 50%=5e6
        e = _Ctx(make_save([stock]))
        r = batch_set_player_pct(e, [2001], 50, target_account="inst")
        self.assertEqual(r[2001]["action"], "diluted")


class TestBatchNpcQuotes(unittest.TestCase):
    def test_sets_amount_buy_and_volume_sell(self):
        e = _Ctx(make_save([make_stock(2001), make_stock(2002)]))
        r = batch_set_npc_quotes(e, [2001, 2002], amount_buy=99999, volume_sell=0)
        for c in (2001, 2002):
            s = e.find(c)
            self.assertEqual(s["Institution"][0]["AmountUsableBuy"], 99999)
            self.assertEqual(s["Institution"][0]["VolumeUsableSell"], 0)
            self.assertEqual(s["Retail"][0]["AmountUsableBuy"], 99999)
            self.assertEqual(s["Retail"][0]["VolumeUsableSell"], 0)
        self.assertTrue(e.modified)

    def test_partial_apply(self):
        e = _Ctx(make_save([make_stock(2001)]))
        batch_set_npc_quotes(e, [2001], amount_buy=5, apply_inst=True, apply_ret=False)
        self.assertEqual(e.find(2001)["Institution"][0]["AmountUsableBuy"], 5)
        # Retail 不改
        self.assertNotEqual(e.find(2001)["Retail"][0]["AmountUsableBuy"], 5)

    def test_none_means_unchanged(self):
        e = _Ctx(make_save([make_stock(2001, amount_usable_buy=123)]))
        batch_set_npc_quotes(e, [2001], amount_buy=None, volume_sell=7)
        # amount_buy 未给，不应改变（仍是 make_stock 默认）
        s = e.find(2001)
        self.assertEqual(s["Institution"][0]["VolumeUsableSell"], 7)


class TestBatchNoticeStyle(unittest.TestCase):
    def test_sets_global_stock_params(self):
        e = _Ctx(make_save([make_stock(2001)]))
        r = batch_set_notice_style(e, [2001], strength=2.0, create_prob=0.5)
        ns = e.data["Market"]["NoticeStyle"]
        self.assertEqual(ns["NormalStockStrength"], 2.0)
        self.assertEqual(ns["NormalStockCreateProb"], 0.5)
        self.assertEqual(r["applied"], 1)
        self.assertTrue(e.modified)

    def test_none_unchanged(self):
        e = _Ctx(make_save([make_stock(2001)]))
        ns_before = dict(e.data["Market"]["NoticeStyle"])
        batch_set_notice_style(e, [2001], strength=None, create_prob=None)
        self.assertEqual(e.data["Market"]["NoticeStyle"], ns_before)


if __name__ == "__main__":
    unittest.main()
