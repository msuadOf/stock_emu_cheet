"""src.core.extra 纯函数单元测试（已迁移到 SaveModel，显示单位）。

这些 extra 功能原本只能通过 TUI harness 间接测试，抽成纯核心后可直接断言。
迁移后函数收 SaveModel/StockModel/InfoModel；本测试用 SaveModel.from_dict(make_save(...))
包裹 helpers 造的原始 dict，断言改用 *_raw（内部值）或显示值。
"""
import math
import unittest

from tests.helpers import make_stock, make_save
from src.core import extra as ex
from src.core.savemodel import SaveModel, InfoModel


def _save(**kw):
    """从 make_save 构造一个 SaveModel（收 StockModel/InfoModel 的 extra 函数）。"""
    return SaveModel.from_dict(make_save(**kw))


class TestNoticeHelpers(unittest.TestCase):
    def test_get_current_game_day(self):
        from src.core.savemodel import StockModel
        stock = StockModel(make_stock(2001, candles=[{"Day": 7}, {"Day": 9}]))
        self.assertEqual(ex.get_current_game_day(stock), 9)
        stock2 = StockModel(make_stock(2001, candles=[]))
        self.assertEqual(ex.get_current_game_day(stock2), 0)

    def test_get_or_create_delisted_pool(self):
        save = _save()
        pool = ex.get_or_create_delisted_pool(save)
        self.assertEqual(pool, {"A": [], "B": []})
        self.assertIs(save._d["Market"]["DelistedPool"], pool)

    def test_build_stock_notice_formula(self):
        n = ex.build_stock_notice(2075, notice_day=10, star=3, strength=2.0, create_prob=0.5)
        self.assertEqual(n["Prob"], 6.0)            # 3*2.0
        self.assertAlmostEqual(n["ReduceProb"], 0.5 / 3)  # create_prob/star
        self.assertEqual(n["Day"], 10)

    def test_append_notice_normal_strips_temp_keys(self):
        save = _save(notice_group={})
        n = ex.build_stock_notice(1, 1, 2, strength=1.0, create_prob=0.1)
        cnt = ex.append_notice_normal(save, [n])
        self.assertEqual(cnt, 1)
        nn = save._d["Market"]["NoticeGroup"]["NoticeNormal"][0]
        self.assertNotIn("_strength", nn)
        self.assertEqual(nn["Code"], 1)

    def test_filter_delisted_candidates(self):
        # 构造一只高负债(>80%)+ 5 条全亏报告的股票
        stock = make_stock(2001, asset_net=10, asset_loan=100, reward_business=0, cost_business=5)
        report_day = lambda d: {"Code": 2001, "Day": d, "RewardBusiness": 0, "RewardOther": 0,
                                "CostBusiness": 5, "CostOther": 0}
        ng = {"NoticeReport": [report_day(i) for i in range(5)]}
        save = SaveModel.from_dict(make_save([stock], notice_group=ng))
        cands = ex.filter_delisted_candidates(save)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0][0], 2001)


class TestPerformanceReport(unittest.TestCase):
    def test_build_and_commit_syncs_info(self):
        stock = make_stock(2001, asset_net=1_000_000_000, asset_loan=500_000_000,
                           reward_business=500_000_000, cost_business=300_000_000)
        info = InfoModel(stock["Info"])
        # build 传入的是显示值（元）；报告内部按内部值（×100）存储
        rep = ex.build_performance_report(2001, info, notice_day=5, star=2,
                                          report_strength=1.5, is_buy=True,
                                          asset_net=900_000_000, asset_loan=400_000_000,
                                          reward_business=600_000_000, reward_other=0,
                                          cost_business=200_000_000, cost_other=0)
        self.assertEqual(rep["Prob"], 3.0)            # 2*1.5
        self.assertAlmostEqual(rep["ReduceProb"], 0.5)  # 1/2
        # 提交后 Info 同步（显示值）
        save = SaveModel.from_dict(make_save([stock]))
        ok = ex.commit_performance_report(save, rep)
        self.assertTrue(ok)
        s = save.find(2001).info
        self.assertEqual(s.asset_net, 900_000_000)
        # NetProfit(显示)= reward - cost = 600M-200M = 400M；内部树里 NetProfit 存内部值 4e10
        self.assertEqual(s._d["NetProfit"], 400_000_000 * 100)
        self.assertIn("PE", s._d)


class TestMoveNpcToRetail(unittest.TestCase):
    def test_transfers_and_reconciles(self):
        # 给一只股票的 HuddleNpc 持仓，转散户后筹码守恒平账（散户/NPC 重新分配）。
        # 关键断言：NPC 持仓被清空，且 主力+散户 == 流通股（平账生效）。
        save = SaveModel.from_dict(make_save(
            [make_stock(2001, volume_flow=10_000_000)],
            huddle_npc=[{"StockPos": [{"Code": 2001, "VolumeUsable": 3000}]}],
            notice_group={"NoticeNormal": [], "NoticeReport": []}))
        moved = ex.move_npc_to_retail(save)
        self.assertIn(2001, moved)
        # NPC 持仓已清空
        for acc in save.npc_account_list("HuddleNpc"):
            for p in acc.get("StockPos", []):
                self.assertNotEqual(p.get("Code"), 2001)
        # 平账：主力+散户(忽略 NPC 已清与玩家 0) 应等于流通股（内部值精确）
        st = save.find(2001)
        flow = st.info._d["VolumeFlow"]
        sh = st._d["Institution"][0].get("VolumeUsableSell", 0) + st._d["Retail"][0].get("VolumeUsableSell", 0)
        self.assertEqual(sh, flow)

    def test_empty_returns_empty(self):
        save = _save()
        self.assertEqual(ex.move_npc_to_retail(save), {})


class TestRectifyMarket(unittest.TestCase):
    def test_balances_sum_hold_to_volume_flow(self):
        # 故意让散户可卖 > 流通股（小差异走顺序扣减）
        stock = make_stock(2001, volume_flow=10_000_000,
                           volume_usable_sell=20_000_000, retail_vol_sell=20_000_000)
        save = SaveModel.from_dict(make_save([stock]))
        summary = ex.rectify_market(save)
        # 校验：主力+散户+NPC+玩家 == 流通股（兜底保证，内部值精确）
        st = save.find(2001)
        flow = st.info._d["VolumeFlow"]
        sh = st._d["Institution"][0].get("VolumeUsableSell", 0) + st._d["Retail"][0].get("VolumeUsableSell", 0)
        self.assertEqual(sh, flow)


class TestCashDividend(unittest.TestCase):
    def test_limits(self):
        info = InfoModel({"AssetNet": 1_000_000, "AssetLoan": 500_000})
        max_total, max_D = ex.cash_dividend_limits(info, total_hand=1000)
        # 总资产=1.5M, ×70%=1.05M - 贷50万=550000; 净资产=1M; min=550000
        self.assertEqual(max_total, 550000)
        # max_D = 550000*10000//1000 = 5500000
        self.assertEqual(max_D, 5_500_000)

    def test_apply_distributes_and_exdiv(self):
        stock = make_stock(2001, price_fact=100000, asset_net=1_000_000, asset_loan=0)
        save = SaveModel.from_dict(make_save([stock], player_amount=1_000_000,
            stock_pos=[{"Code": 2001, "Amount": 0, "VolumeUsable": 1000}]))
        vols = {"player": 1000, "inst": 0, "ret": 0}
        D_int = 100  # 「分」单位
        ex.apply_cash_dividend(save, 2001, save.find(2001), vols, D_int)
        # 总手数=1000, add=1000*100//10000=10 内部元；玩家 Amount=1e6+10
        self.assertEqual(save.player._d["Amount"], 1_000_010)
        # 除息降股价：D_int=100(分/100股) => 每股 1分 => PriceFact - 1
        # （回归守护：旧实现误用 D_int 当分/股，会跌 100；与 test_v2_features 的 TUI 路径
        #  PriceFact==998 同口径，core 必须一致）
        self.assertEqual(save.find(2001).info.price_fact_raw, 100000 - 1)

    def test_exdiv_drop_matches_tui_int_D(self):
        # D=2.0 元/100股 => D_int=200 => 每股跌 2 分。TUI test_v2_features 钉死 1000-2=998。
        stock = make_stock(2001, price_fact=1000, price_init=1000,
                           volume_total=1_000_000_000, volume_flow=1_000_000_000,
                           asset_net=5_000_000_000, asset_loan=0)
        save = SaveModel.from_dict(make_save([stock], player_amount=0))
        vols = ex.collect_dividend_vols(save, 2001, save.find(2001))
        ex.apply_cash_dividend(save, 2001, save.find(2001), vols, D_int=int(2.0 * 100))
        self.assertEqual(save.find(2001).info.price_fact_raw, 998)

    def test_collect_dividend_vols_includes_player_and_npc(self):
        # 回归守护：collect_dividend_vols 必须读玩家真实持仓 + 5 类 NPC 持仓，
        # 不能把 player 硬编码为 0 或漏 NPC（旧 CLI/GUI 的 bug）。
        stock = make_stock(2001, volume_usable_sell=300, retail_vol_sell=0)
        save = SaveModel.from_dict(make_save([stock],
            stock_pos=[{"Code": 2001, "Amount": 0, "VolumeUsable": 500}],
            huddle_npc=[{"StockPos": [{"Code": 2001, "VolumeUsable": 200}]}]))
        vols = ex.collect_dividend_vols(save, 2001, save.find(2001))
        self.assertEqual(vols["player"], 500)
        self.assertEqual(vols["inst"], 300)
        self.assertEqual(vols["HuddleNpc"], 200)
        # 其余 NPC 类无持仓 → 0
        self.assertEqual(vols["AloneNpc"], 0)


class TestStockDividend(unittest.TestCase):
    def test_scales_holdings_and_price(self):
        stock = make_stock(2001, price_fact=100000, volume_total=100_000_000,
                           volume_flow=100_000_000)
        save = SaveModel.from_dict(make_save([stock],
            stock_pos=[{"Code": 2001, "Amount": 0, "VolumeUsable": 1000}]))
        nf, nt, np2 = ex.apply_stock_dividend(save, 2001, save.find(2001), X=10)
        # 10送10 => r=2.0
        self.assertEqual(nf, 200_000_000)
        self.assertEqual(nt, 200_000_000)
        self.assertEqual(np2, 50_000)  # 100000/2
        # 玩家持仓翻倍
        self.assertEqual(save.player._d["StockPos"][0]["VolumeUsable"], 2000)


class TestPrivatePlacement(unittest.TestCase):
    def test_compute(self):
        candles = [{"Close": 1000}] * 5   # 显示均价 10 元/股
        avg20, py, pi, ns, cost = ex.compute_placement(candles, price_fact=100000,
                                                        ratio=0.8, amount_yuan=10000)
        self.assertAlmostEqual(avg20, 10.0)
        self.assertAlmostEqual(py, 8.0)         # 10 * 0.8
        self.assertEqual(pi, 800)               # 8.0*100
        self.assertEqual(ns, int(10000 / 8.0 * 100))
        self.assertEqual(cost, 1_000_000)       # 10000*100

    def test_apply_deducts_player_and_adds_shares(self):
        stock = make_stock(2001, price_fact=100000, volume_total=100_000_000, volume_flow=100_000_000)
        save = SaveModel.from_dict(make_save([stock], player_amount=1_000_000))
        ns = 5000
        cost = 400000
        ex.apply_private_placement(save, 2001, save.find(2001), ns, cost, candles=[])
        self.assertEqual(save.player._d["Amount"], 1_000_000 - 400000)
        self.assertEqual(save.find(2001).info.volume_flow_raw, 100_000_000 + 5000)
        # 玩家持仓登记
        pos = [p for p in save.player._d["StockPos"] if p["Code"] == 2001]
        self.assertEqual(pos[0]["VolumeUsable"], 5000)


class TestDelist(unittest.TestCase):
    def test_to_a_sets_rate_limit(self):
        save = SaveModel.from_dict(make_save([make_stock(2001)]))
        ok = ex.delist_to_a(save, 2001)
        self.assertTrue(ok)
        self.assertEqual(save.find(2001).info.rate_limit, 0.05)
        pool = ex.get_or_create_delisted_pool(save)
        self.assertIn(2001, pool["A"])

    def test_to_b_removes_stock_and_player_position(self):
        save = SaveModel.from_dict(make_save([make_stock(2001)],
            notice_group={"NoticeNormal": [], "NoticeReport": []},
            stock_pos=[{"Code": 2001, "Amount": 0, "VolumeUsable": 100}]))
        stock, positions = ex.delist_to_b(save, 2001)
        self.assertIsNotNone(stock)
        self.assertEqual(positions, [(0, 100)])
        self.assertIsNone(save.find(2001))
        pool = ex.get_or_create_delisted_pool(save)
        self.assertIn(2001, pool["B"])


class TestIssueStock(unittest.TestCase):
    def test_build_restore_and_attach(self):
        save = _save()
        ns_stock = ex.build_new_stock_restore(
            new_code=10511, sector_limit=True, sector_rate_limit=0.1,
            volume_total=10_000_000, volume_flow=10_000_000,
            asset_net=500_000_000, asset_loan=300_000_000,
            reward_business=100_000_000, reward_other=10_000_000,
            cost_business=60_000_000, cost_other=20_000_000,
            net_profit=30_000_000, raw_price=1000, bourse_num=1, sector_num=50,
        )
        ex.attach_stock_to_market(save, ns_stock, raw_price=1000, sector_num=50, bourse_num=1,
                                  mode="restore", restore_code=None)
        self.assertIsNotNone(save.find(10511))
        self.assertEqual(len(save.find(10511).info._d["Candles"]), 1)
        # Sectors 挂接
        sect_codes = [s["Code"] for s in save._d["Market"]["Sectors"]]
        self.assertIn(50, sect_codes)

    def test_build_custom_has_51_49_holdings(self):
        ns_stock = ex.build_new_stock_custom(
            new_code=10512, default_info={"Limit": True, "RateLimit": 0.1},
            total_shares_internal=1_000_000, floats_internal=1_000_000,
            raw_price=1000, inst_vol_internal=510, inst_buy=1000,
            retail_vol_internal=490, retail_buy=2000, bourse_num=1, sector_num=50,
        )
        self.assertEqual(ns_stock["Institution"][0]["VolumeUsableSell"], 510)
        self.assertEqual(ns_stock["Retail"][0]["VolumeUsableSell"], 490)


if __name__ == "__main__":
    unittest.main()
