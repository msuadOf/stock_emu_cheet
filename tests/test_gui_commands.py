"""GUI 后端 commands.py 的接线测试。

pytauri（Rust/Python 桥）在测试环境里装不上，这里用 stub 让 commands.py 可导入，
从而验证命令层接线：summary 取 last_close、set_price 不双重×100、set_pe 等不崩。
（真实 pytauri 环境下这些函数行为一致——stub 只替换装饰器为直通。）
"""
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

# ---- stub pytauri（仅测试用：把 @commands.command() 变成直通装饰器）----
if "pytauri" not in sys.modules:
    _mod = types.ModuleType("pytauri")

    class _Commands:                       # noqa: N801 - 模拟 pytauri.Commands
        def command(self):
            def deco(fn):
                return fn
            return deco
    _mod.Commands = _Commands
    sys.modules["pytauri"] = _mod

from src.gui.backend import commands          # noqa: E402
from src.core.editor import find_stock        # noqa: E402
from src.core.savemodel import InfoModel      # noqa: E402
from tests.helpers import make_stock, make_save   # noqa: E402


def _write_save(td, data):
    f = Path(td) / "t.sav"
    f.write_text(json.dumps(data), encoding="utf-8")
    return str(f)


class TestStockSummary(unittest.TestCase):
    def test_summary_uses_last_close_not_pricefact(self):
        info_d = make_stock(2001, price_fact=2538)["Info"]
        info_d["Candles"][-1]["Close"] = 6907          # 真实价 ≠ PriceFact
        s = commands._stock_summary(InfoModel(info_d), 2001)
        self.assertEqual(s["last_close"], 6907)        # 取 K 线，内部值
        self.assertEqual(s["code"], 2001)


class TestSetPrice(unittest.TestCase):
    """设昨收：传显示元，后端写最后 K 线 Close=yuan*100，且不崩、不双重×100。"""

    def test_set_price_fact_writes_last_close_correctly(self):
        async def run():
            data = make_save([make_stock(2001, price_fact=2538)])
            with tempfile.TemporaryDirectory() as td:
                f = _write_save(td, data)
                ret = await commands.set_price(
                    {"file": f, "code": 2001, "yuan": 12.50, "field": "fact", "save": True})
                self.assertEqual(ret["last_close"], 1250)          # 12.50*100，非 125000
                info = find_stock(json.loads(Path(f).read_text(encoding="utf-8")), 2001)["Info"]
                self.assertEqual(info["Candles"][-1]["Close"], 1250)   # K 线已同步
                self.assertEqual(info["PriceFact"], 1250)              # PriceFact 也同步
        import asyncio
        asyncio.get_event_loop().run_until_complete(run())


class TestSetValuationsNoCrash(unittest.TestCase):
    """set_pe/set_pb/set_debt 以前传裸 dict 给 InfoModel-only 的 core 会崩；现应正常。"""

    def test_set_pe_roundtrips(self):
        async def run():
            data = make_save([make_stock(2001, price_fact=100000, volume_total=100_000_000,
                                         reward_business=500_000_000, cost_business=300_000_000)])
            with tempfile.TemporaryDirectory() as td:
                f = _write_save(td, data)
                ret = await commands.set_pe({"file": f, "code": 2001, "target": 5.0, "save": False})
                self.assertAlmostEqual(ret["pe"], 5.0, places=2)
        import asyncio
        asyncio.get_event_loop().run_until_complete(run())

    def test_set_pb_no_crash(self):
        async def run():
            data = make_save([make_stock(2001, price_fact=100000, volume_total=100_000_000,
                                         asset_net=1_000_000_000)])
            with tempfile.TemporaryDirectory() as td:
                f = _write_save(td, data)
                ret = await commands.set_pb({"file": f, "code": 2001, "target": 1.0, "save": False})
                self.assertAlmostEqual(ret["pb"], 1.0, places=2)
        import asyncio
        asyncio.get_event_loop().run_until_complete(run())

    def test_set_debt_no_crash(self):
        async def run():
            data = make_save([make_stock(2001, asset_net=1_000_000_000, asset_loan=0)])
            with tempfile.TemporaryDirectory() as td:
                f = _write_save(td, data)
                ret = await commands.set_debt({"file": f, "code": 2001, "ratio_pct": 30, "save": False})
                self.assertGreater(ret["pe"], 0)   # 只要能返回 summary 即未崩
        import asyncio
        asyncio.get_event_loop().run_until_complete(run())


if __name__ == "__main__":
    unittest.main()
