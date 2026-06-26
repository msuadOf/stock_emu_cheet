"""测试基础设施：虚拟存档构造 + 交互 mock，全程不碰真实 .sav 文件。

导入被测模块用的是 sse 这个别名（stock save editor），避免和 tests 包里的
stock_save_editor 顶层模块名混淆。注意 tests 不是被测包，这里只放工具。
"""
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

# 以文件绝对路径加载被测模块，命名为 sse，避免与 tests 包内命名冲突。
# 重构后 TUI 交互层集中在 src/tui/app.py（单一模块 = sse），核心逻辑在 src/core。
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
_spec = importlib.util.spec_from_file_location("sse", _REPO / "src" / "tui" / "app.py")
sse = importlib.util.module_from_spec(_spec)
sys.modules["sse"] = sse
_spec.loader.exec_module(sse)


# ----------------------------------------------------------------------
# 虚拟存档构造
# ----------------------------------------------------------------------
def make_stock(code, price_init=100000, price_fact=100000, rate_limit=0.10,
               volume_total=100_000_000, volume_flow=100_000_000,
               asset_net=5_000_000_000, asset_loan=2_000_000_000,
               reward_business=500_000_000, reward_other=0,
               cost_business=300_000_000, cost_other=0,
               volume_usable_sell=None, amount_usable_buy=10_000_000,
               retail_vol_sell=None, retail_amt_buy=5_000_000,
               candles=None, hot=None):
    """构造一只股票的存档片段，全部参数有合理默认值。

    volume_usable_sell 默认给一个正值（非 -1 无限制），方便测试筹码守恒逻辑。
    """
    if volume_usable_sell is None:
        volume_usable_sell = 20_000_000
    if retail_vol_sell is None:
        retail_vol_sell = 10_000_000
    info = {
        "Code": code,
        "PriceInit": price_init,
        "PriceFact": price_fact,
        "RateLimit": rate_limit,
        "Limit": False,
        "VolumeTotal": volume_total,
        "VolumeFlow": volume_flow,
        "Bourse": "SH",
        "Sector": "科技",
        "AssetNet": asset_net,
        "AssetLoan": asset_loan,
        "RewardBusiness": reward_business,
        "RewardOther": reward_other,
        "CostBusiness": cost_business,
        "CostOther": cost_other,
        "ProfitNetPrev": reward_business - cost_business,
        # Prev / Min 同步字段，验证防回滚逻辑
        "AssetNetPrev": asset_net,
        "AssetLoanPrev": asset_loan,
        "RewardBusinessPrev": reward_business,
        "RewardOtherPrev": reward_other,
        "CostBusinessPrev": cost_business,
        "CostOtherPrev": cost_other,
        "AssetNetMin": 0,
        "AssetLoanMin": 0,
        "RewardBusinessMin": 0,
        "RewardOtherMin": 0,
        "CostBusinessMin": 0,
        "CostOtherMin": 0,
        # K 线：内部值/100=显示价
        "Candles": candles if candles is not None else [
            {"Day": 1, "Open": price_fact, "Close": price_fact,
             "High": price_fact + 1000, "Low": price_fact - 1000,
             "Volume": 1000, "Amount": 1_000_000},
            {"Day": 2, "Open": price_fact, "Close": price_fact,
             "High": price_fact + 1000, "Low": price_fact - 1000,
             "Volume": 1000, "Amount": 1_000_000},
        ],
    }
    stock = {
        "Info": info,
        "Institution": [{
            "VolumeUsableSell": volume_usable_sell,
            "AmountUsableBuy": amount_usable_buy,
        }],
        "Retail": [{
            "VolumeUsableSell": retail_vol_sell,
            "AmountUsableBuy": retail_amt_buy,
        }],
    }
    if hot is not None:
        stock["HotMoney"] = [hot]
    return stock


def make_save(stocks=None, stock_pos=None, player_amount=1_000_000,
              notice_style=None, notice_group=None, huddle_npc=None,
              trade_type=None):
    """构造一份完整存档 dict。默认 3 只股票用于中位数计算。"""
    if stocks is None:
        stocks = [make_stock(2001), make_stock(2002), make_stock(2003)]
    return {
        "Market": {
            "Stocks": stocks,
            "NoticeStyle": notice_style if notice_style is not None else {
                "NormalMarketStrength": 1.0, "NormalMarketCreateProb": 0.0,
                "NormalSectorStrength": 1.0, "NormalSectorCreateProb": 0.0,
                "NormalStockStrength": 1.0, "NormalStockCreateProb": 0.0,
                "RankCreateExchangeRate": 1, "ReportCreateDay": 5,
            },
            "NoticeGroup": notice_group if notice_group is not None else {"a": [1, 2, 3]},
            "HuddleNpc": huddle_npc if huddle_npc is not None else [
                {"StockPos": [{"Code": 2001}, {"Code": 2002}, {"Code": 2003}]}
            ],
        },
        "Player": {
            "StockPos": stock_pos if stock_pos is not None else [],
            "Amount": player_amount,
            "TradeType": trade_type if trade_type is not None else [1, 2, 3],
        },
    }


# ----------------------------------------------------------------------
# 临时存档目录（供 E2E 走 main() 的目录扫描用）
# ----------------------------------------------------------------------
def make_save_tree(slots, root=None):
    """在临时目录里造出真实的多 slot 存档结构，模拟游戏存档目录布局。

    目录布局:
        <root>/
            slot_0/xxx.sav   <- 每个子目录含 .sav 文件才会被 find_save_dirs 识别
            slot_1/yyy.sav
            ...

    slots: [{name, file, data}] 列表。返回 root 路径（Path）。
    root=None 时新建临时目录，调用方负责清理（删整个 root）。
    """
    root = Path(root) if root else Path(tempfile.mkdtemp(prefix="sse_tree_"))
    root.mkdir(parents=True, exist_ok=True)
    for s in slots:
        sub = root / s["name"]
        sub.mkdir(parents=True, exist_ok=True)
        with open(sub / s["file"], "w", encoding="utf-8") as f:
            json.dump(s["data"], f, ensure_ascii=False)
    return root


# ----------------------------------------------------------------------
# 临时存档文件
# ----------------------------------------------------------------------
class TempSave:
    """把虚拟存档写到临时文件，返回 (Editor 实例, 路径)。

    用完自动清理临时目录。Editor 本身的 save() 会写回同一个临时文件。
    """

    def __init__(self, data):
        self._data = data
        self.tmpdir = tempfile.mkdtemp(prefix="sse_test_")
        self.path = Path(self.tmpdir) / "test.sav"

    def __enter__(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False)
        return sse.Editor(self.path), self.path

    def __exit__(self, *exc):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        return False


def fresh_editor(data):
    """直接返回一个已 load 的 Editor，数据在内存里（不落盘）。

    适合只验证内存字段变化、不关心磁盘写入的用例。
    """
    import shutil
    tmpdir = tempfile.mkdtemp(prefix="sse_test_")
    path = Path(tmpdir) / "test.sav"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    e = sse.Editor(path)
    e.load()
    # 把临时目录记到实例上，由测试清理；这里不自动删，交由调用方
    return e


# ----------------------------------------------------------------------
# 交互 mock
# ----------------------------------------------------------------------
def _queue_inputs(inputs):
    """把 ['a','b',None] 变成一个 input mock；None 触发 EOFError（模拟结束）。"""
    it = iter(inputs)

    def fake_input(prompt=""):
        try:
            v = next(it)
        except StopIteration:
            raise EOFError("输入已耗尽：测试喂入的输入不够")
        if v is None:
            raise EOFError("输入已耗尽（None）")
        return v

    return fake_input


@contextmanager
def harness(inputs, game_running=False, capture_print=True, argv=None):
    """一次性 mock 掉所有交互副作用。

    - input: 按顺序消费 inputs
    - print: 吞掉输出（capture_print=True 时收集到 ctx.out）
    - clear / pause: 变成 no-op
    - is_game_running: 返回 game_running
    - argv: 若给定，patch sys.argv（argv[0] 是程序名，其余是参数），
            使走 main()/parse_args 时能注入命令行参数（如 -d 存档目录）
    - main 的 KeyboardInterrupt / 通用异常仍按原样抛出

    注意：select_save_dir/select_save_file 走真实的目录扫描，**不 mock**。
    E2E 测试需在临时目录里造出真实的子目录 + .sav 文件结构。
    """
    out = io.StringIO()
    patches = [
        mock.patch("sse.input", _queue_inputs(inputs)),
        mock.patch("sse.clear", lambda *a, **k: None),
        mock.patch("sse.pause", lambda *a, **k: None),
        mock.patch("sse.is_game_running", lambda *a, **k: game_running),
    ]
    if argv is not None:
        patches.append(mock.patch.object(sys, "argv", argv))
    if capture_print:
        patches.append(mock.patch("sse.print", lambda *a, **k: out.write(" ".join(map(str, a)) + (k.get("end", "\n") if k else "\n"))))

    for p in patches:
        p.start()
    try:
        ctx = lambda: None
        ctx.out = out
        yield ctx
    finally:
        for p in patches:
            p.stop()


# 复用 unittest，测试文件 import 后直接继承即可
BaseTestCase = unittest.TestCase
