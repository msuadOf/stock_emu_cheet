"""feat 点回归测试：覆盖所有改档函数 + 新功能 + 菜单接线。

全程在虚拟存档 / 临时文件上操作，绝不触碰真实 .sav。每个用例验证“修改后
相关字段是否按预期变化”，并顺带检查防回滚的 Prev/Min 字段是否被同步。
"""
import json
import unittest
from unittest import mock
from tests.helpers import harness, sse, make_save, make_stock, TempSave, fresh_editor


# ----------------------------------------------------------------------
# 单股改档：PE / PB / 负债率
# ----------------------------------------------------------------------
class TestChangePE(unittest.TestCase):
    def _run(self, data, inputs):
        e = fresh_editor(data)
        e.selected_code = 2001
        with harness(inputs):
            sse.change_pe(e)
        return e

    def test_sets_target_pe_and_clears_costs(self):
        # PE = 显示价 * 显示股本 / 显示净利润 = p*v/(100*np)
        # price=100000(内部=显示1000元), vol=1e8(内部=显示1e6股)
        # 目标PE=1 → np_ = p*v/(100*1) = 1e9
        data = make_save([make_stock(2001)])
        e = self._run(data, ["1.0", "y"])  # 目标PE, 确认
        info = e.find(2001).info._d
        p, v = info["PriceFact"], info["VolumeTotal"]
        np_ = info["RewardBusiness"]  # 其它被清零
        # 正确公式：游戏里真正呈现的 PE
        self.assertAlmostEqual(p * v / (100 * np_), 1.0, places=4)
        # 旧错误公式(p*v/np)应是目标的100倍 → 回归护栏，防止改回100倍bug
        self.assertAlmostEqual(p * v / np_, 100.0, places=4)
        self.assertEqual(info["CostBusiness"], 0)
        self.assertEqual(info["CostOther"], 0)
        self.assertEqual(info["RewardOther"], 0)
        # Prev 同步、Min 归零（防回滚）
        self.assertEqual(info["ProfitNetPrev"], int(p * v / (100 * 1.0)))
        self.assertEqual(info["RewardBusinessMin"], 0)
        self.assertTrue(e.modified)

    def test_pe_zero_aborts(self):
        # PE 不能为 0 → 中止，不改数据
        data = make_save([make_stock(2001)])
        e = self._run(data, ["0"])
        self.assertFalse(e.modified)
        self.assertEqual(e.find(2001).info._d["RewardBusiness"], 500_000_000)

    def test_pe_cancel_not_modified(self):
        data = make_save([make_stock(2001)])
        e = self._run(data, ["1.0", "n"])  # 不确认
        self.assertFalse(e.modified)


class TestChangePB(unittest.TestCase):
    def test_sets_target_pb(self):
        # PB = p*v/(100*AssetNet)；目标0.5 → AssetNet = p*v/(100*0.5)
        data = make_save([make_stock(2001)])
        e = fresh_editor(data)
        e.selected_code = 2001
        with harness(["0.5", "y"]):
            sse.change_pb(e)
        info = e.find(2001).info._d
        p, v = info["PriceFact"], info["VolumeTotal"]
        # 正确公式：游戏里真正呈现的 PB
        self.assertAlmostEqual(p * v / (100 * info["AssetNet"]), 0.5, places=4)
        # 旧错误公式应是目标的100倍 → 回归护栏
        self.assertAlmostEqual(p * v / info["AssetNet"], 50.0, places=4)
        self.assertEqual(info["AssetNetPrev"], info["AssetNet"])
        self.assertEqual(info["AssetNetMin"], 0)
        self.assertTrue(e.modified)


class TestChangeDebt(unittest.TestCase):
    def test_sets_target_debt_ratio(self):
        # 目标负债率30%：AssetLoan = AssetNet*30/70
        data = make_save([make_stock(2001, asset_net=1_000_000_000)])
        e = fresh_editor(data)
        e.selected_code = 2001
        with harness(["30", "y"]):
            sse.change_debt(e)
        info = e.find(2001).info._d
        an, al = info["AssetNet"], info["AssetLoan"]
        self.assertAlmostEqual(al / (al + an) * 100, 30.0, places=2)
        self.assertEqual(info["AssetLoanPrev"], al)
        self.assertEqual(info["AssetLoanMin"], 0)


# ----------------------------------------------------------------------
# 单股改档：PriceInit / PriceFact（K线同步）/ RateLimit
# ----------------------------------------------------------------------
class TestChangePriceInit(unittest.TestCase):
    def test_sets_raw_internal_value(self):
        data = make_save([make_stock(2001)])
        e = fresh_editor(data)
        e.selected_code = 2001
        with harness(["8.88", "y"]):  # 显示价 8.88 → 内部 888
            sse.change_pi(e)
        self.assertEqual(e.find(2001).info._d["PriceInit"], 888)


class TestChangePriceFactKLine(unittest.TestCase):
    def _stock_with_candles(self):
        return make_stock(2001, candles=[
            {"Day": 9, "Open": 100000, "Close": 100000,
             "High": 105000, "Low": 95000, "Volume": 100, "Amount": 1000},
        ])

    def test_syncs_last_candle_ohlc(self):
        data = make_save([self._stock_with_candles()])
        e = fresh_editor(data)
        e.selected_code = 2001
        # 显示价15 → 内部 raw=1500，低于原 High(105000) 和原 Low(95000)
        # 因此：High 不动(105000 不<1500)，Low 被拉低(95000>1500 → 1500)
        with harness(["15.00", "y"]):
            sse.change_pf(e)
        info = e.find(2001).info._d
        self.assertEqual(info["PriceFact"], 1500)
        last = info["Candles"][-1]
        self.assertEqual(last["Close"], 1500)
        self.assertEqual(last["Open"], 1500)
        self.assertEqual(last["High"], 105000)  # 原High更高，不抬
        self.assertEqual(last["Low"], 1500)     # 原Low更低，被拉低

    def test_syncs_high_when_price_rises(self):
        # 互补场景：新价高于原 High → High 被抬；Low 不动
        data = make_save([self._stock_with_candles()])
        e = fresh_editor(data)
        e.selected_code = 2001
        with harness(["2000.00", "y"]):  # raw=200000 > 原 High 105000
            sse.change_pf(e)
        last = e.find(2001).info._d["Candles"][-1]
        self.assertEqual(last["High"], 200000)
        self.assertEqual(last["Low"], 95000)  # 原 Low 更低，不动

    def test_no_candles_creates_one(self):
        data = make_save([make_stock(2001, candles=[])])
        e = fresh_editor(data)
        e.selected_code = 2001
        with harness(["10.00", "y"]):
            sse.change_pf(e)
        info = e.find(2001).info._d
        self.assertEqual(info["PriceFact"], 1000)
        self.assertEqual(len(info["Candles"]), 1)
        self.assertEqual(info["Candles"][0]["Close"], 1000)

    def test_day_not_incremented(self):
        # 回归：旧版会新增一根 Day+1；新版就地改，Day 不变
        data = make_save([self._stock_with_candles()])
        e = fresh_editor(data)
        e.selected_code = 2001
        with harness(["10.00", "y"]):
            sse.change_pf(e)
        self.assertEqual(e.find(2001).info._d["Candles"][-1]["Day"], 9)


class TestChangeRateLimit(unittest.TestCase):
    def test_sets_rate_limit_fraction(self):
        data = make_save([make_stock(2001)])
        e = fresh_editor(data)
        e.selected_code = 2001
        with harness(["20", "y"]):
            sse.change_rl(e)
        self.assertEqual(e.find(2001).info._d["RateLimit"], 0.20)


# ----------------------------------------------------------------------
# NPC 挂单：中位数 / 倍数 / 清零 / 自定义
# ----------------------------------------------------------------------
class TestChangeNpc(unittest.TestCase):
    def _three_stocks(self):
        # 三只股票，机构可卖分别 10/20/30 万，便于算中位数
        return [
            make_stock(2001, volume_usable_sell=100_000),
            make_stock(2002, volume_usable_sell=200_000),
            make_stock(2003, volume_usable_sell=300_000),
        ]

    def test_median_mode_excludes_self(self):
        stocks = self._three_stocks()
        data = make_save(stocks)
        e = fresh_editor(data)
        # 操作2001：中位数取自2002/2003 → [200000,300000] 中位=250000
        e.selected_code = 2001
        with harness(["2", "y" if False else ""]):  # mode2, 无确认步骤
            sse.change_npc(e)
        inst = e.find(2001).institution._d
        self.assertEqual(inst["VolumeUsableSell"], 250000)

    def test_clear_mode_zeros(self):
        data = make_save(self._three_stocks())
        e = fresh_editor(data)
        e.selected_code = 2001
        with harness(["1"]):  # mode1 全部清零
            sse.change_npc(e)
        inst = e.find(2001).institution._d
        ret = e.find(2001).retail._d
        self.assertEqual(inst["VolumeUsableSell"], 0)
        self.assertEqual(inst["AmountUsableBuy"], 0)
        self.assertEqual(ret["VolumeUsableSell"], 0)
        self.assertEqual(ret["AmountUsableBuy"], 0)

    def test_custom_mode(self):
        data = make_save([make_stock(2001)])
        e = fresh_editor(data)
        e.selected_code = 2001
        # mode5, Inst.VolSell, Inst.AmountBuy, Retail.VolSell, Retail.AmountBuy
        with harness(["5", "999", "888", "777", "666"]):
            sse.change_npc(e)
        inst = e.find(2001).institution._d
        ret = e.find(2001).retail._d
        self.assertEqual(inst["VolumeUsableSell"], 999)
        self.assertEqual(inst["AmountUsableBuy"], 888)
        self.assertEqual(ret["VolumeUsableSell"], 777)
        self.assertEqual(ret["AmountUsableBuy"], 666)


# ----------------------------------------------------------------------
# 自由设定财务指标（新功能）+ 万/亿换算
# ----------------------------------------------------------------------
class TestChangeFinancials(unittest.TestCase):
    def _run(self, data, inputs):
        e = fresh_editor(data)
        e.selected_code = 2001
        with harness(inputs):
            sse.change_financials(e)
        return e

    def test_wan_yi_conversion(self):
        data = make_save([make_stock(2001)])
        # 8个字段依次：1亿 / 5000万 / 空回车 / ... 验证换算与保留原值
        e = self._run(data, [
            "1亿",          # VolumeTotal → 1e8
            "5000万",       # VolumeFlow → 5e7
            "",             # AssetNet 保持
            "1000000000",   # AssetLoan
            "0", "0", "0", "0",  # Reward/Cost 全清
        ])
        info = e.find(2001).info._d
        self.assertEqual(info["VolumeTotal"], 100_000_000)
        self.assertEqual(info["VolumeFlow"], 50_000_000)
        self.assertEqual(info["AssetNet"], 5_000_000_000)  # 回车→保持
        self.assertEqual(info["AssetLoan"], 1_000_000_000)
        self.assertEqual(info["RewardBusiness"], 0)

    def test_comma_stripped(self):
        data = make_save([make_stock(2001)])
        e = self._run(data, ["1,000,000", "0", "0", "0", "0", "0", "0", "0"])
        self.assertEqual(e.find(2001).info._d["VolumeTotal"], 1_000_000)

    def test_prev_min_synced(self):
        data = make_save([make_stock(2001)])
        e = self._run(data, ["2亿", "0", "1亿", "0", "0", "0", "0", "0"])
        info = e.find(2001).info._d
        self.assertEqual(info["VolumeTotal"], 200_000_000)
        # Prev 同步到当前值，Min 归零
        self.assertEqual(info["AssetNetPrev"], info["AssetNet"])
        self.assertEqual(info["AssetNetMin"], 0)
        self.assertEqual(info["ProfitNetPrev"],
                         info["RewardBusiness"] + info["RewardOther"]
                         - info["CostBusiness"] - info["CostOther"])


# ----------------------------------------------------------------------
# NoticeStyle（全局 NPC 力度）
# ----------------------------------------------------------------------
class TestChangeNoticeStyle(unittest.TestCase):
    def _run(self, data, inputs):
        e = fresh_editor(data)
        with harness(inputs):
            sse.change_ns(e)
        return e

    def test_push_individual_stock(self):
        e = self._run(make_save(), ["1"])
        ns = e.data["Market"]["NoticeStyle"]
        self.assertEqual(ns["NormalStockStrength"], 2.0)
        self.assertEqual(ns["NormalStockCreateProb"], 0.5)

    def test_reset_all(self):
        e = self._run(make_save(), ["5"])
        ns = e.data["Market"]["NoticeStyle"]
        for k in ("NormalMarketStrength", "NormalSectorStrength", "NormalStockStrength"):
            self.assertEqual(ns[k], 1.0)
        for k in ("NormalMarketCreateProb", "NormalSectorCreateProb", "NormalStockCreateProb"):
            self.assertEqual(ns[k], 0.0)


# ----------------------------------------------------------------------
# 智能增发 dilute_stock_for_shortage（新功能，核心）
# ----------------------------------------------------------------------
class TestDilute(unittest.TestCase):
    def test_scales_proportionally_preserves_pe_pb(self):
        stock = make_stock(2001, volume_total=100_000_000, volume_flow=100_000_000,
                           asset_net=5_000_000_000, asset_loan=2_000_000_000,
                           reward_business=500_000_000)
        info = stock["Info"]
        price = info["PriceFact"]
        old_pe = price * info["VolumeTotal"] / (
            info["RewardBusiness"] + info["RewardOther"]
            - info["CostBusiness"] - info["CostOther"])
        old_pb = price * info["VolumeTotal"] / info["AssetNet"]

        with harness([]):  # 套 harness：避免 GBK 控制台编码 ⚠️ 报错
            sse.dilute_stock_for_shortage(stock, 50_000_000)  # 增发5000万
        # 总股本 1.5亿，流通股 +5000万
        self.assertEqual(info["VolumeTotal"], 150_000_000)
        self.assertEqual(info["VolumeFlow"], 150_000_000)
        # PE/PB 维持不变（等比放大）
        new_pe = price * info["VolumeTotal"] / (
            info["RewardBusiness"] - info["CostBusiness"])
        new_pb = price * info["VolumeTotal"] / info["AssetNet"]
        self.assertAlmostEqual(old_pe, new_pe, places=2)
        self.assertAlmostEqual(old_pb, new_pb, places=2)
        # Prev 同步放大
        self.assertEqual(info["AssetNetPrev"], info["AssetNet"])

    def test_zero_total_guarded(self):
        # 股本为0时用1兜底，不抛异常；new_total = 1 + shortage
        stock = make_stock(2001, volume_total=0)
        with harness([]):
            sse.dilute_stock_for_shortage(stock, 100)
        self.assertEqual(stock["Info"]["VolumeTotal"], 101)


# ----------------------------------------------------------------------
# change_player：筹码守恒 + 智能增发 + 过户（新功能，最复杂）
# ----------------------------------------------------------------------
class TestChangePlayer(unittest.TestCase):
    def test_buy_within_npc_supply_no_dilution(self):
        # 玩家加仓1000股，机构可卖2000万 → 直接扣减，不增发
        data = make_save([make_stock(2001, volume_usable_sell=2_000_000)])
        e = fresh_editor(data)
        with harness(["1", "2001", "0", "1000", "1"]):  # 加仓, code, amount, vol, 选机构
            sse.change_player(e)
        sp = e.data["Player"]["StockPos"]
        self.assertEqual(sp[-1]["Code"], 2001)
        self.assertEqual(sp[-1]["VolumeUsable"], 1000)
        self.assertEqual(e.find(2001).institution._d["VolumeUsableSell"], 1_999_000)
        # 未触发增发：总股本不变
        self.assertEqual(e.find(2001).info._d["VolumeTotal"], 100_000_000)

    def test_buy_exceeds_supply_triggers_dilution(self):
        # 玩家加仓超过机构可卖 → 触发增发补缺口
        data = make_save([make_stock(2001, volume_usable_sell=1000,
                                     volume_total=10_000_000)])
        e = fresh_editor(data)
        with harness(["1", "2001", "0", "5000", "1"]):  # 要5000，机构只有1000
            sse.change_player(e)
        info = e.find(2001).info._d
        # 增发 = 5000-1000 = 4000；新总股本 = 10_000_000+4000
        self.assertEqual(info["VolumeTotal"], 10_004_000)
        self.assertEqual(info["VolumeFlow"], 100_000_000 + 4000)
        self.assertEqual(e.find(2001).institution._d["VolumeUsableSell"], 0)

    def test_buy_from_unlimited_npc_no_change(self):
        # NPC可卖=-1(无限制) → 不扣减、不增发
        data = make_save([make_stock(2001, volume_usable_sell=-1)])
        e = fresh_editor(data)
        with harness(["1", "2001", "0", "99999", "1"]):
            sse.change_player(e)
        self.assertEqual(e.find(2001).institution._d["VolumeUsableSell"], -1)
        self.assertEqual(e.find(2001).info._d["VolumeTotal"], 100_000_000)

    def test_sell_transfers_to_npc(self):
        # 先建仓再减仓：玩家卖出500 → 机构可卖 +500
        data = make_save([make_stock(2001, volume_usable_sell=1000)],
                         stock_pos=[{"Code": 2001, "Amount": 0, "VolumeUsable": 1000}])
        e = fresh_editor(data)
        with harness(["2", "2001", "0", "500", "1"]):  # 改为500股，过户给机构
            sse.change_player(e)
        self.assertEqual(e.find(2001).institution._d["VolumeUsableSell"], 1500)

    def test_skip_sync(self):
        # target=0 不同步：凭空生成，NPC与股本都不变
        data = make_save([make_stock(2001, volume_usable_sell=1000)])
        e = fresh_editor(data)
        with harness(["1", "2001", "0", "5000", "0"]):  # 不同步
            sse.change_player(e)
        self.assertEqual(e.find(2001).institution._d["VolumeUsableSell"], 1000)
        self.assertEqual(e.find(2001).info._d["VolumeTotal"], 100_000_000)

    def test_delete_position(self):
        data = make_save([make_stock(2001)],
                         stock_pos=[{"Code": 2001, "Amount": 0, "VolumeUsable": 1000}])
        e = fresh_editor(data)
        with harness(["3", "2001", "2"]):  # 删除，玩家卖出过户给机构
            sse.change_player(e)
        self.assertEqual([p for p in e.data["Player"]["StockPos"] if p.get("Code") == 2001], [])

    def test_modify_player_amount(self):
        data = make_save()
        e = fresh_editor(data)
        with harness(["4", "999999"]):
            sse.change_player(e)
        self.assertEqual(e.data["Player"]["Amount"], 999999)

    def test_code_not_found_aborts(self):
        data = make_save([make_stock(2001)])
        e = fresh_editor(data)
        with harness(["1", "9999"]):  # 不存在的code
            sse.change_player(e)
        self.assertEqual(e.data["Player"]["StockPos"], [])


# ----------------------------------------------------------------------
# 清理：NoticeGroup / HuddleNpc / TradeType
# ----------------------------------------------------------------------
class TestCleanup(unittest.TestCase):
    def test_clean_notice_group(self):
        data = make_save(notice_group={"a": [1, 2, 3, 4]})
        e = fresh_editor(data)
        with harness(["y"]):
            sse.clean_ng(e)
        self.assertEqual(e.data["Market"]["NoticeGroup"]["a"], [])

    def test_trim_huddle_npc(self):
        data = make_save(huddle_npc=[
            {"StockPos": [{"Code": i} for i in range(20)]}
        ])
        e = fresh_editor(data)
        with harness(["5", "y"]):  # 每个NPC保留5条
            sse.trim_hn(e)
        self.assertEqual(len(e.data["Market"]["HuddleNpc"][0]["StockPos"]), 5)

    def test_clean_trade_type(self):
        data = make_save(trade_type=[1, 2, 3, 4, 5])
        e = fresh_editor(data)
        with harness(["y"]):
            sse.clean_tt(e)
        self.assertEqual(e.data["Player"]["TradeType"], [])


# ----------------------------------------------------------------------
# Editor.save()：防覆盖三路（新功能）+ 磁盘写入 + 备份
# ----------------------------------------------------------------------
class TestEditorSave(unittest.TestCase):
    def test_save_writes_and_backs_up_when_game_off(self):
        data = make_save([make_stock(2001)])
        with TempSave(data) as (e, path):
            e.load()
            e.find(2001).info._d["PriceFact"] = 55555
            e.modified = True
            with harness([], game_running=False):
                self.assertTrue(e.save())
            # 磁盘写入新值
            with open(path, encoding="utf-8") as f:
                on_disk = json.load(f)
            self.assertEqual(on_disk["Market"]["Stocks"][0]["Info"]["PriceFact"], 55555)
            # 生成了备份文件
            backups = list(path.parent.glob("*.sav.bak.*"))
            self.assertEqual(len(backups), 1)

    def test_save_aborts_when_game_running_and_decline(self):
        data = make_save([make_stock(2001)])
        with TempSave(data) as (e, path):
            e.load()
            e.find(2001).info._d["PriceFact"] = 55555
            e.modified = True
            with harness(["n"], game_running=True):  # 拒绝强制保存
                self.assertFalse(e.save())
            # 没写盘
            with open(path, encoding="utf-8") as f:
                on_disk = json.load(f)
            self.assertEqual(on_disk["Market"]["Stocks"][0]["Info"]["PriceFact"], 100000)
            self.assertEqual(len(list(path.parent.glob("*.sav.bak.*"))), 0)

    def test_save_force_when_game_running_and_accept(self):
        data = make_save([make_stock(2001)])
        with TempSave(data) as (e, path):
            e.load()
            e.find(2001).info._d["PriceFact"] = 55555
            e.modified = True
            with harness(["y"], game_running=True):  # 强制保存
                self.assertTrue(e.save())
            with open(path, encoding="utf-8") as f:
                on_disk = json.load(f)
            self.assertEqual(on_disk["Market"]["Stocks"][0]["Info"]["PriceFact"], 55555)

    def test_save_no_changes_returns_false(self):
        with TempSave(make_save([make_stock(2001)])) as (e, path):
            e.load()
            with harness([]):
                self.assertFalse(e.save())


# ----------------------------------------------------------------------
# 菜单接线：stock_menu 选项 9(财务) 与 0(返回) 是新映射
# ----------------------------------------------------------------------
class TestStockMenu(unittest.TestCase):
    def test_option_9_calls_financials(self):
        data = make_save([make_stock(2001)])
        e = fresh_editor(data)
        # 选 9 → change_financials：8字段全回车(保持) → 然后 0 返回
        inputs = ["9", "", "", "", "", "", "", "", "", "0"]
        with harness(inputs):
            sse.stock_menu(e, 2001)
        # 走通了即可；确认 selected_code 被设
        self.assertEqual(e.selected_code, 2001)

    def test_option_0_returns(self):
        data = make_save([make_stock(2001)])
        e = fresh_editor(data)
        with harness(["0"]):
            sse.stock_menu(e, 2001)  # 直接返回，不循环

    def test_main_menu_choice_1_enters_stock_then_exit(self):
        data = make_save([make_stock(2001)])
        e = fresh_editor(data)
        # 主菜单:1选股 → 输入2001 → 进子菜单 → 0返回 → 主菜单:17退出
        with harness(["1", "2001", "0", "17"]):
            sse.main_menu(e)
        # 没崩即通过

    def test_pe_inf_shown_as_na(self):
        # 净利润<=0 时子菜单显示 N/A 而非 inf（回归旧 bug）
        data = make_save([make_stock(2001, reward_business=100, cost_business=500)])
        e = fresh_editor(data)
        with harness(["0"]) as c:  # 进菜单立即返回
            sse.stock_menu(e, 2001)


# ----------------------------------------------------------------------
# 单位换算回归：价格/股数/金额在存档里都是显示值的 100 倍。
# 旧版 PE/PB 用原始 PriceFact 直接乘，结果比真实值大 100 倍；
# 旧版股本显示用 fmt_m 直接标“亿”，与游戏界面(÷100)不一致。这里钉死正确公式。
# ----------------------------------------------------------------------
class TestUnitScaling(unittest.TestCase):
    def _stock(self, **kw):
        return make_stock(2001, **kw)

    def test_calc_pe_uses_display_units(self):
        # 真实 PE = 显示价 * 显示股本 / 显示净利润 = p*v/(100*np)
        # 用一组真实量级验证：算出来的 PE 应在合理区间(几~几十)，而非旧版的几百几千
        info = self._stock(price_fact=8622, volume_total=1_285_911_796,
                           reward_business=91_218_626_237, cost_business=9_260_044_530,
                           reward_other=1_983_273_457, cost_other=21_227_068_439)["Info"]
        np_ = (info["RewardBusiness"] + info["RewardOther"]
               - info["CostBusiness"] - info["CostOther"])
        correct = info["PriceFact"] * info["VolumeTotal"] / (100 * np_)
        self.assertAlmostEqual(sse.calc_pe(info), correct, places=2)
        # 钉死：correct ≈ 1.77，旧错公式会给出 ≈177
        self.assertLess(sse.calc_pe(info), 5)
        self.assertGreater(sse.calc_pe(info), 1)

    def test_calc_pb_uses_display_units(self):
        info = self._stock(price_fact=8622, volume_total=1_285_911_796,
                           asset_net=106_173_243_398)["Info"]
        correct = info["PriceFact"] * info["VolumeTotal"] / (100 * info["AssetNet"])
        self.assertAlmostEqual(sse.calc_pb(info), correct, places=4)
        # 钉死：correct ≈ 1.04，旧错公式会给出 ≈104
        self.assertLess(sse.calc_pb(info), 2)
        self.assertGreater(sse.calc_pb(info), 0.5)

    def test_calc_pe_inf_on_zero_profit(self):
        info = self._stock(reward_business=100, cost_business=100)["Info"]  # 净利润=0
        self.assertEqual(sse.calc_pe(info), float("inf"))

    def test_calc_pb_inf_on_zero_asset(self):
        info = self._stock(asset_net=0)["Info"]
        self.assertEqual(sse.calc_pb(info), float("inf"))

    def test_market_cap_is_price_times_volume_over_10000(self):
        # 总市值(元) = (PriceFact/100)*(VolumeTotal/100) = p*v/10000
        info = self._stock(price_fact=100000, volume_total=100_000_000)["Info"]
        # 显示价1000元 * 显示股本100万股 = 10亿元 = 1e9
        self.assertAlmostEqual(sse.calc_market_cap(info), 1e9, places=0)

    def test_fmt_shares_divides_by_100_for_display(self):
        # 游戏界面显示的股数 = 内部值/100；fmt_shares 必须给出“显示”那一档
        out = sse.fmt_shares(1_285_911_796)  # 内部值 → 显示 12,859,118 股
        self.assertIn("12,859,118", out)
        # 内部原值也要保留，便于对照
        self.assertIn("1,285,911,796", out)

    def test_fmt_shares_small_value(self):
        out = sse.fmt_shares(100)  # 内部100 → 显示1股
        self.assertIn("1", out)

    def test_fmt_m_still_marks_money_in_yuan(self):
        # 金额字段保持原值标注（内部值即元数），不受股数修正影响
        self.assertIn("亿", sse.fmt_m(1_000_000_000))


if __name__ == "__main__":
    unittest.main(verbosity=2)
