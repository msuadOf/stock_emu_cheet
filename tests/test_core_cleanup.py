"""cleanup_ops 纯核心测试：清空公告 / 清空交易历史 / 裁剪 HuddleNpc。"""
import unittest
from tests.helpers import make_stock, make_save
from src.core import clear_notice_group, clear_trade_type, trim_huddle_npc
from src.core.savemodel import SaveModel


class TestCleanup(unittest.TestCase):
    def test_clear_notice_group_dict(self):
        save = SaveModel.from_dict(make_save([make_stock(2001)],
            notice_group={"NoticeNormal": [1, 2, 3], "NoticeReport": [4, 5]}))
        r = clear_notice_group(save)
        self.assertEqual(r["before"], 5)
        self.assertEqual(r["form"], "dict")
        ng = save._d["Market"]["NoticeGroup"]
        self.assertEqual(ng["NoticeNormal"], [])
        self.assertEqual(ng["NoticeReport"], [])

    def test_clear_notice_group_list(self):
        save = SaveModel.from_dict({"Market": {"Stocks": [], "NoticeGroup": [1, 2]}})
        r = clear_notice_group(save)
        self.assertEqual(r["before"], 2)
        self.assertEqual(save._d["Market"]["NoticeGroup"], [])

    def test_clear_notice_group_empty(self):
        save = SaveModel.from_dict(make_save([make_stock(2001)],
            notice_group={"NoticeNormal": []}))
        r = clear_notice_group(save)
        self.assertEqual(r["before"], 0)

    def test_clear_trade_type(self):
        save = SaveModel.from_dict(make_save([make_stock(2001)], trade_type=[1, 2, 3, 4]))
        r = clear_trade_type(save)
        self.assertEqual(r["before"], 4)
        self.assertEqual(save.player.trade_type, [])

    def test_trim_huddle_npc(self):
        save = SaveModel.from_dict(make_save([make_stock(2001)],
            huddle_npc=[{"StockPos": [{"Code": i} for i in range(20)]}]))
        r = trim_huddle_npc(save, keep=5)
        self.assertEqual(r["before"], 20)
        self.assertEqual(r["after"], 5)
        self.assertEqual(len(save._d["Market"]["HuddleNpc"][0]["StockPos"]), 5)

    def test_trim_huddle_npc_zero(self):
        save = SaveModel.from_dict(make_save([make_stock(2001)],
            huddle_npc=[{"StockPos": [{"Code": i} for i in range(10)]}]))
        r = trim_huddle_npc(save, keep=0)
        self.assertEqual(r["after"], 0)


if __name__ == "__main__":
    unittest.main()
