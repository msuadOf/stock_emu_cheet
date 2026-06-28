"""src.core 批量操作函数的单元测试（已迁移到 SaveModel，显示单位）。

batch_set_player_pct / batch_set_npc_quotes / batch_set_notice_style。
函数收 SaveModel，本测试用 SaveModel.from_dict(make_save(...)) 包裹。
"""
import unittest

from tests.helpers import make_stock, make_save
from src.core import (
    batch_set_player_pct, batch_set_npc_quotes, batch_set_notice_style,
    codes_by_sector,
)
from src.core.savemodel import SaveModel


class TestBatchPlayerPct(unittest.TestCase):
    def test_sets_position_to_flow_pct_display(self):
        # volume_flow=100_000_000 内部 → 显示流通 1e6 股；pct=10 → 持仓 1e5 显示股
        stock = make_stock(2001, volume_flow=100_000_000, volume_total=100_000_000,
                           volume_usable_sell=500_000_000)
        save = SaveModel.from_dict(make_save([stock]))
        r = batch_set_player_pct(save, [2001], 10, target_account="inst")
        self.assertIn(2001, r)
        self.assertEqual(r[2001]["volume"], 100_000)               # 显示股
        self.assertEqual(r[2001]["volume_raw"], 10_000_000)        # 内部
        pos = save.player.find_position(2001)
        self.assertEqual(pos.volume_usable_raw, 10_000_000)

    def test_nonexistent_code_skipped(self):
        save = SaveModel.from_dict(make_save([make_stock(2001)]))
        r = batch_set_player_pct(save, [9999], 10)
        self.assertEqual(r, {})

    def test_multiple_codes(self):
        stocks = [make_stock(c, volume_flow=100_000_000, volume_usable_sell=500_000_000)
                  for c in (2001, 2002, 2003)]
        save = SaveModel.from_dict(make_save(stocks))
        r = batch_set_player_pct(save, [2001, 2002, 2003], 50, target_account="inst")
        self.assertEqual(set(r.keys()), {2001, 2002, 2003})
        for info in r.values():
            self.assertEqual(info["volume"], 500_000)              # 显示股

    def test_conservation_no_dilution(self):
        # 流通 1e6 显示股；持仓 50% = 5e5 显示股；从可卖(主力充足)扣
        stock = make_stock(2001, volume_flow=10_000_000, volume_total=10_000_000,
                           volume_usable_sell=8_000_000, retail_vol_sell=8_000_000)
        save = SaveModel.from_dict(make_save([stock]))
        flow_raw_before = save.find(2001).info.volume_flow_raw
        r = batch_set_player_pct(save, [2001], 50, target_account="inst")
        self.assertEqual(r[2001]["volume"], 50_000)                # 显示股，精确
        self.assertEqual(save.find(2001).info.volume_flow_raw, flow_raw_before)  # 不增发
        taken = r[2001]["taken_from"]
        self.assertEqual(taken["inst"] + taken["ret"], 50_000)

    def test_falls_through_to_secondary(self):
        # 主力可卖(显示)不够，从散户补
        stock = make_stock(2001, volume_flow=10_000_000, volume_total=10_000_000,
                           volume_usable_sell=1_000_000, retail_vol_sell=9_000_000)
        save = SaveModel.from_dict(make_save([stock]))
        r = batch_set_player_pct(save, [2001], 50, target_account="inst")  # 要 5e5 显示股
        taken = r[2001]["taken_from"]
        # 主力可卖 1e6 内部=1e4 显示股；散户 9e6 内部=9e4 显示股
        self.assertEqual(taken["inst"], 10_000)
        self.assertEqual(taken["ret"], 40_000)
        self.assertEqual(r[2001]["action"], "transferred")

    def test_shortage_recorded_no_dilution(self):
        # 主力+散户可卖都不够，记录 shortage 但不增发
        stock = make_stock(2001, volume_flow=100_000_000, volume_total=100_000_000,
                           volume_usable_sell=1_000, retail_vol_sell=1_000)
        save = SaveModel.from_dict(make_save([stock]))
        flow_before = save.find(2001).info.volume_flow_raw
        r = batch_set_player_pct(save, [2001], 50, target_account="inst")
        self.assertEqual(r[2001]["action"], "shortage")
        self.assertGreater(r[2001]["shortfall_shares"], 0)
        self.assertEqual(save.find(2001).info.volume_flow_raw, flow_before)  # 不增发
        # sellable_ratio_pct 反映可卖占比极小
        self.assertLess(r[2001]["sellable_ratio_pct"], 1.0)


class TestBatchNpcQuotes(unittest.TestCase):
    def test_sets_amount_buy_and_volume_sell(self):
        save = SaveModel.from_dict(make_save([make_stock(2001), make_stock(2002)]))
        r = batch_set_npc_quotes(save, [2001, 2002], amount_buy=99999, volume_sell=0)
        for c in (2001, 2002):
            s = save.find(c)
            self.assertEqual(s.institution.amount_usable_buy, 99999)
            self.assertEqual(s.institution.volume_usable_sell, 0)
            self.assertEqual(s.retail.amount_usable_buy, 99999)
            self.assertEqual(s.retail.volume_usable_sell, 0)

    def test_partial_apply(self):
        save = SaveModel.from_dict(make_save([make_stock(2001)]))
        batch_set_npc_quotes(save, [2001], amount_buy=5, apply_inst=True, apply_ret=False)
        self.assertEqual(save.find(2001).institution.amount_usable_buy, 5)
        # Retail 不改（保持 make_stock 默认的显示值）
        self.assertNotEqual(save.find(2001).retail.amount_usable_buy, 5)

    def test_none_means_unchanged(self):
        save = SaveModel.from_dict(make_save([make_stock(2001, amount_usable_buy=12300)]))
        # amount_usable_buy=12300 内部 → 显示 123；不改 amount_buy，只改 volume_sell
        batch_set_npc_quotes(save, [2001], amount_buy=None, volume_sell=7)
        self.assertEqual(save.find(2001).institution.amount_usable_buy, 123)
        self.assertEqual(save.find(2001).institution.volume_usable_sell, 7)


class TestBatchNoticeStyle(unittest.TestCase):
    def test_sets_global_stock_params(self):
        save = SaveModel.from_dict(make_save([make_stock(2001)]))
        r = batch_set_notice_style(save, [2001], strength=2.0, create_prob=0.5)
        ns = save.notice_style
        self.assertEqual(ns["NormalStockStrength"], 2.0)
        self.assertEqual(ns["NormalStockCreateProb"], 0.5)
        self.assertEqual(r["applied"], 1)

    def test_none_unchanged(self):
        save = SaveModel.from_dict(make_save([make_stock(2001)]))
        ns_before = dict(save.notice_style)
        batch_set_notice_style(save, [2001], strength=None, create_prob=None)
        self.assertEqual(save.notice_style, ns_before)


class TestBatchStrategies(unittest.TestCase):
    """扣仓位策略：balance_ir / ret_then_inst / hot / npc_proportional。

    make_stock 的 volume_usable_sell/retail_vol_sell/hot[N].VolumeUsableSell 都是内部值，
    getter 返回显示值 = 内部/100。下方用 r[2001]["volume"] 拿实际目标持仓（显示股）断言守恒，
    避免手算单位换算。
    """

    def test_balance_ir_proportional(self):
        # 主力可卖显示 3e4、散户 1e4（3:1）；balance_ir 按比例分摊目标持仓
        stock = make_stock(2001, volume_flow=10_000_000, volume_total=10_000_000,
                           volume_usable_sell=3_000_000, retail_vol_sell=1_000_000)
        save = SaveModel.from_dict(make_save([stock]))
        r = batch_set_player_pct(save, [2001], 20, strategy="balance_ir")
        taken = r[2001]["taken_from"]
        target = r[2001]["volume"]
        self.assertEqual(r[2001]["action"], "transferred")
        self.assertEqual(taken["inst"] + taken["ret"], target)         # 守恒
        # 主力:散户 ≈ 3:1
        self.assertAlmostEqual(taken["inst"] * 1e4, taken["ret"] * 3e4, delta=max(1, target // 100))

    def test_ret_then_inst_order(self):
        # 先散户后机构：散户可卖显示 2e4，目标持仓 < 散户可卖 → 只扣散户
        stock = make_stock(2001, volume_flow=10_000_000, volume_total=10_000_000,
                           volume_usable_sell=5_000_000, retail_vol_sell=2_000_000)
        save = SaveModel.from_dict(make_save([stock]))
        r = batch_set_player_pct(save, [2001], 5, strategy="ret_then_inst")  # 要 ~1e4
        taken = r[2001]["taken_from"]
        self.assertEqual(taken["ret"], r[2001]["volume"])
        self.assertEqual(taken["inst"], 0)

    def test_ret_then_inst_falls_through(self):
        # 散户不够，补机构：散户可卖显示 1e4，目标 > 散户 → 散户扣满 + 机构补差
        stock = make_stock(2001, volume_flow=10_000_000, volume_total=10_000_000,
                           volume_usable_sell=5_000_000, retail_vol_sell=1_000_000)
        save = SaveModel.from_dict(make_save([stock]))
        r = batch_set_player_pct(save, [2001], 20, strategy="ret_then_inst")  # 要 ~2e4
        taken = r[2001]["taken_from"]
        target = r[2001]["volume"]
        self.assertEqual(taken["ret"], 10_000)                         # 散户扣满（1e4 显示）
        self.assertEqual(taken["inst"], target - 10_000)               # 机构补差

    def test_hot_strategy(self):
        # hot 优先：游资可卖显示 5e4，目标 ~1e4 → 只扣游资（修原 bug：hot 现在真能扣）
        hot = {"VolumeUsableSell": 5_000_000}
        stock = make_stock(2001, volume_flow=10_000_000, volume_total=10_000_000,
                           volume_usable_sell=1_000_000, retail_vol_sell=1_000_000, hot=hot)
        save = SaveModel.from_dict(make_save([stock]))
        r = batch_set_player_pct(save, [2001], 5, strategy="hot")
        taken = r[2001]["taken_from"]
        self.assertEqual(taken["hot"], r[2001]["volume"])
        self.assertEqual(taken["inst"], 0)
        self.assertEqual(r[2001]["action"], "transferred")

    def test_hot_falls_through(self):
        # 游资不够，补主力：游资可卖显示 1e4，目标 ~2e4 → 游资扣满 + 主力补差
        hot = {"VolumeUsableSell": 1_000_000}
        stock = make_stock(2001, volume_flow=10_000_000, volume_total=10_000_000,
                           volume_usable_sell=5_000_000, retail_vol_sell=1_000_000, hot=hot)
        save = SaveModel.from_dict(make_save([stock]))
        r = batch_set_player_pct(save, [2001], 20, strategy="hot")
        taken = r[2001]["taken_from"]
        target = r[2001]["volume"]
        self.assertEqual(taken["hot"], 10_000)
        self.assertEqual(taken["inst"], target - 10_000)

    def test_npc_proportional(self):
        # NPC 账户可卖显示 6e4 + 2e4（3:1）；npc_proportional 按比例分摊目标持仓
        stock = make_stock(2001, volume_flow=10_000_000, volume_total=10_000_000,
                           volume_usable_sell=0, retail_vol_sell=0)
        stock["HuddleNpc"] = [{"VolumeUsableSell": 6_000_000}]
        stock["AloneNpc"] = [{"VolumeUsableSell": 2_000_000}]
        save = SaveModel.from_dict(make_save([stock]))
        r = batch_set_player_pct(save, [2001], 20, strategy="npc_proportional")
        taken = r[2001]["taken_from"]
        target = r[2001]["volume"]
        self.assertEqual(r[2001]["action"], "transferred")
        npc_total = sum(v for k, v in taken.items() if k not in ("inst", "ret"))
        self.assertEqual(npc_total, target)                            # 守恒
        self.assertGreater(taken["HuddleNpc"], taken["AloneNpc"])     # 6e4 > 2e4 比例

    def test_strategy_overrides_target_account(self):
        # 传 strategy 时忽略 target_account
        stock = make_stock(2001, volume_flow=10_000_000, volume_total=10_000_000,
                           volume_usable_sell=5_000_000, retail_vol_sell=5_000_000)
        save = SaveModel.from_dict(make_save([stock]))
        r = batch_set_player_pct(save, [2001], 5, target_account="inst", strategy="ret")
        taken = r[2001]["taken_from"]
        self.assertGreater(taken["ret"], 0)
        self.assertEqual(taken["inst"], 0)


class TestSectorBatch(unittest.TestCase):
    """按板块(Sector)批量：batch 函数 sector 参数 + codes_by_sector。"""

    def test_codes_by_sector(self):
        s1 = make_stock(2001); s1["Info"]["Sector"] = 20
        s2 = make_stock(2002); s2["Info"]["Sector"] = 30
        s3 = make_stock(2003); s3["Info"]["Sector"] = 20
        save = SaveModel.from_dict(make_save([s1, s2, s3]))
        self.assertEqual(codes_by_sector(save._d, 20), [2001, 2003])
        self.assertEqual(codes_by_sector(save._d, 30), [2002])
        self.assertEqual(codes_by_sector(save._d, 99), [])
        self.assertEqual(codes_by_sector(save._d, None), [2001, 2002, 2003])

    def test_batch_player_pct_sector(self):
        # sector 给定时只作用于该板块；另一板块不受影响
        s1 = make_stock(2001, volume_flow=10_000_000, volume_usable_sell=5_000_000)
        s1["Info"]["Sector"] = 20
        s2 = make_stock(2002, volume_flow=10_000_000, volume_usable_sell=5_000_000)
        s2["Info"]["Sector"] = 30
        save = SaveModel.from_dict(make_save([s1, s2]))
        r = batch_set_player_pct(save, pct=10, sector=20)   # 只改板块20
        self.assertEqual(set(r.keys()), {2001})             # 2002 不在结果
        self.assertIsNone(save.player.find_position(2002))  # 2002 持仓未被创建

    def test_batch_npc_quotes_sector(self):
        s1 = make_stock(2001, volume_usable_sell=1_000_000); s1["Info"]["Sector"] = 20
        s2 = make_stock(2002, volume_usable_sell=1_000_000); s2["Info"]["Sector"] = 30
        save = SaveModel.from_dict(make_save([s1, s2]))
        r = batch_set_npc_quotes(save, volume_sell=0, sector=20)
        self.assertEqual(set(r.keys()), {2001})
        self.assertEqual(save.find(2001).institution.volume_usable_sell_raw, 0)
        self.assertEqual(save.find(2002).institution.volume_usable_sell_raw, 1_000_000)  # 板块30未改

    def test_batch_notice_style_sector_count(self):
        s1 = make_stock(2001); s1["Info"]["Sector"] = 20
        s2 = make_stock(2002); s2["Info"]["Sector"] = 20
        s3 = make_stock(2003); s3["Info"]["Sector"] = 30
        save = SaveModel.from_dict(make_save([s1, s2, s3]))
        r = batch_set_notice_style(save, strength=2.0, sector=20)
        self.assertEqual(r["applied"], 2)   # 板块20 有2只


if __name__ == "__main__":
    unittest.main()
