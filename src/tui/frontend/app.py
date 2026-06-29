"""StocksMainForceSimulator 存档编辑器 —— 终极防覆盖增强版（TUI 入口）。

本模块是**唯一的** TUI 交互层，被测试基础设施 ``tests/helpers.py`` 以
``importlib`` 加载为名为 ``sse`` 的模块。所有会裸调 ``input/print/clear/pause/
confirm`` 的函数都集中在这里，从而保证 ``mock.patch("sse.input" / "sse.print" /
"sse.clear" / "sse.pause" / "sse.is_game_running" / "sse.subprocess.run")`` 仍能命中
（架构约束 2，已实测）。

纯业务逻辑放在 ``src/core``（``Editor`` 除外）。``Editor`` 类留在这里，因为其
``save()`` 内部要调 ``is_game_running()`` 与 ``confirm()``，必须解析到 ``sse.*``。
"""
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ---- 从共享业务后端导入纯函数/常量（单向依赖：tui -> core）----
from src.core import (
    DEFAULT_SAVE_DIR,
    GAME_PROCESS_NAME,
    SECTOR_MAP,
    BOURSE_MAP,
    fmt_p, fmt_v, fmt_m, fmt_shares,
    calc_pe, calc_pb, calc_market_cap,
    last_close_raw,
    is_game_running as _core_is_game_running,
    find_save_dirs,
    list_saves,
    set_target_pe, set_target_pb, set_target_debt_ratio,
    set_price_init, set_price_fact_sync_candles, set_rate_limit,
    set_npc_quotes_by_median, clear_npc_quotes,
    apply_notice_style,
    dilute_for_shortage,
)
from src.core.extra import (
    move_npc_to_retail, collect_npc_holdings, rectify_market,
    compute_placement, apply_private_placement,
)
from src.core.savemodel import SaveModel, SHARE_SCALE
from src.tui.backend.view_text import format_stock_detail


# ====== ANSI 颜色 ======
class C:
    RESET = chr(27) + "[0m"
    BOLD = chr(27) + "[1m"
    DIM = chr(27) + "[2m"
    RED = chr(27) + "[91m"
    GREEN = chr(27) + "[92m"
    YELLOW = chr(27) + "[93m"
    BLUE = chr(27) + "[94m"
    CYAN = chr(27) + "[96m"
    WHITE = chr(27) + "[97m"


def enable_ansi():
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


def col(color, text):
    return color + str(text) + C.RESET


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def hr(c="=", w=70):
    print(c * w)


def pause(m="Press Enter..."):
    input(col(C.DIM, m))


def prompt(t, d=None):
    s = (" [" + str(d) + "]") if d is not None else ""
    v = input(col(C.CYAN, t + s + ": ")).strip()
    return v if v else d


def prompt_int(t, d=None, default=None, mn=None, mx=None, extract_code=False):
    if default is not None and d is None:
        d = default
    while True:
        v = prompt(t, d)
        try:
            if extract_code and isinstance(v, str):
                digits = re.sub(r'\D', '', v)
                if not digits:
                    print(col(C.RED, "  Err: 未找到有效数字")); continue
                v = digits

            n = int(v) if v != "" else (d if d is not None else 0)
            if mn is not None and n < mn:
                print(col(C.RED, "  Err: < " + str(mn))); continue
            if mx is not None and n > mx:
                print(col(C.RED, "  Err: > " + str(mx))); continue
            return n
        except (ValueError, TypeError):
            print(col(C.RED, "  Err: not int"))


def prompt_float(t, d=None, default=None, mn=None, mx=None):
    if default is not None and d is None:
        d = default
    while True:
        v = prompt(t, d)
        try:
            n = float(v) if v != "" else (d if d is not None else 0.0)
            if mn is not None and n < mn:
                print(col(C.RED, "  Err: < " + str(mn))); continue
            if mx is not None and n > mx:
                print(col(C.RED, "  Err: > " + str(mx))); continue
            return n
        except (ValueError, TypeError):
            print(col(C.RED, "  Err: not num"))


def confirm(t, no=True):
    sfx = " [y/N]" if no else " [Y/n]"
    v = input(col(C.YELLOW, t + sfx + ": ")).strip().lower()
    return (v in ("y", "yes")) if v else (not no)


# ====== 进程检测（本地薄封装：让测试 patch 的 sse.is_game_running / sse.subprocess.run 命中）======
# 这里重新实现而非直接 from core import，使函数 __globals__ 即 sse，
# 从而 mock.patch("sse.is_game_running") / mock.patch("sse.subprocess.run") 生效。
def is_game_running():
    try:
        result = subprocess.run(
            f'tasklist /FI "IMAGENAME eq {GAME_PROCESS_NAME}"',
            capture_output=True, text=True, shell=True,
        )
        return GAME_PROCESS_NAME.lower() in result.stdout.lower()
    except Exception:
        return False


def select_save_dir(base_dir=DEFAULT_SAVE_DIR):
    base_dir = Path(base_dir)
    ds = find_save_dirs(base_dir)
    if not ds:
        print(col(C.RED, "No save dirs in " + str(base_dir))); return None
    if len(ds) == 1:
        return ds[0]
    print(col(C.BOLD, "Save dirs:"))
    for i, d in enumerate(ds):
        print("  " + str(i + 1) + ". " + d.name)
    return ds[prompt_int("Dir", default=1, mn=1, mx=len(ds)) - 1]


def select_save_file(d):
    ss = list_saves(d)
    if not ss:
        print(col(C.RED, "No saves")); return None
    if len(ss) == 1:
        return ss[0]
    print(col(C.BOLD, "Saves in " + d.name + ":"))
    for i, s in enumerate(ss):
        kb = s.stat().st_size / 1024
        mt = datetime.fromtimestamp(s.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        print("  " + str(i + 1) + ". " + s.name.ljust(30) + " " + str(round(kb, 1)).rjust(8) + "KB  " + mt)
    return ss[prompt_int("Save", default=1, mn=1, mx=len(ss)) - 1]


# ====== Editor（留在此处：save() 内部 confirm/is_game_running 必须解析到 sse.*）======
class Editor:
    """交互式 Editor：持 SaveModel（字段语义）+ 交互式 save()（confirm/进程检测）。

    ``load()`` 读 .sav 构造 ``SaveModel``（内部值，与文件一一对应）并暴露为 ``self.model``。
    为兼容现有测试与交互壳，``.data`` / ``.find`` / ``.stocks`` / ``.codes`` 仍以
    **裸 dict** 形式暴露（``.data`` = ``model._d``），阶段 B2 会切到 StockModel。
    交互 ``save()`` 的 confirm/is_game_running/print 留在本模块（``__globals__`` = sse，
    ``mock.patch("sse.*")`` 命中）；落盘委托 ``core.Editor.save``（纯逻辑）。
    """
    def __init__(self, path):
        self.path = Path(path)
        self.bak = self.path.with_suffix(".sav.bak." + datetime.now().strftime("%Y%m%d_%H%M%S"))
        self.model = None
        self.modified = False

    @property
    def data(self):
        # 过渡：仍返回裸 dict（= model._d），保持 67 处断言兼容；阶段 B2 切 StockModel。
        return self.model._d if self.model is not None else None

    def load(self):
        with open(self.path, "r", encoding="utf-8") as f:
            self.model = SaveModel.from_dict(json.load(f))
        self.modified = False
        return self.model

    def save(self):
        if not self.modified:
            return False

        # 保存前检测游戏是否在运行，改为「警告并允许强制保存」，不再死板拦截
        if is_game_running():
            print(col(C.RED, "\n  ⚠️ 警告：检测到游戏进程正在后台运行！"))
            print(col(C.YELLOW, "  如果现在保存，游戏退出时的'自动保存'可能会用内存旧数据覆盖你的修改！"))
            print(col(C.YELLOW, "  建议彻底结束游戏进程后再来保存。"))
            if not confirm("是否无视警告，强制保存？", no=True):
                return False

        # 落盘委托 core.Editor（纯：备份 + model.write + 进程守卫已由上方交互处理）
        from src.core.editor import Editor as _CoreEditor
        core_ed = _CoreEditor(self.path)
        core_ed.save(self.model, force=True, is_game_running=lambda: False)
        self.modified = False
        return True

    def stocks(self):
        return self.model.stocks

    def find(self, code):
        return self.model.find(code)

    def codes(self):
        return self.model.codes()

# ====== 以下为交互/展示/菜单函数（搬自原单文件；注释统一为 [extra]）======
def need_stock(e):
    code = getattr(e, "selected_code", None)
    if not code: print(col(C.RED, "  请先选股票")); pause(); return None
    s = e.find(code)
    if not s: print(col(C.RED, "  X" + str(code) + " 不存在")); pause(); return None
    return s

def change_pe(e):
    s = need_stock(e)
    if not s: return
    info = s.info
    cur_pe = calc_pe(info._d)
    print("  当前 PE = " + ("N/A (净利润<=0)" if cur_pe == float("inf") else str(round(cur_pe, 4))))
    print("  PE = 显示价 * 显示股本 / 显示净利润")
    print("    = (PriceFact/100)*(VolumeTotal/100) / (NetProfit/100)")
    print("    = PriceFact * VolumeTotal / (100 * NetProfit)")
    print("  PE 越小越安全, 负数表示亏损")
    print("  PE = 0.1: 极低,股票被严重低估")
    print("  PE = 1.0: 正常,股票估值合理")
    print("  PE = 10: 较高,股票可能被高估")
    print("  PE = 负数: 公司亏损,股票风险高")
    print()
    target = prompt_float("目标 PE (0.1=极小, 1=正常, 10=较大)", default="0.1")
    if target == 0: print(col(C.RED, "  PE 不能为 0")); pause(); return
    # 展示用：目标净利润（显示值）= 显示价 × 显示股本 / 目标PE（与 core.set_target_pe 同公式）
    target_np = info.price_fact * info.volume_total / target
    if abs(target_np) > 1e15: print(col(C.YELLOW, "  警告: 值 > 1e15 可能有浮点精度问题"))
    print("  需要设置 RewardBusiness = " + str(int(round(target_np))))
    if not confirm("确认修改?", no=False): return
    # 转调 core: set_target_pe(InfoModel, 目标PE) 按显示值反推净利润并写入（同步 Prev/Min）
    set_target_pe(info, target)
    e.modified = True
    print(col(C.GREEN, "  新 PE = " + str(round(calc_pe(info._d), 4))))
    pause()

def change_pb(e):
    s = need_stock(e)
    if not s: return
    info = s.info
    cur_pb = calc_pb(info._d)
    print("  当前 PB = " + ("N/A (净资产<=0)" if cur_pb == float("inf") else str(round(cur_pb, 4))))
    print("  PB = 显示价 * 显示股本 / 显示净资产")
    print("    = (PriceFact/100)*(VolumeTotal/100) / (AssetNet/100)")
    print("    = PriceFact * VolumeTotal / (100 * AssetNet)")
    print("  PB < 1 表示净资产相对股价高, PB > 1 表示净资产相对股价低")
    print("  PB = 0.1: 极低,股价远低于净资产")
    print("  PB = 1.0: 正常,股价等于净资产")
    print("  PB = 10: 较高,股价远高于净资产")
    print()
    target = prompt_float("目标 PB (0.1=极小, 1=正常, 10=较大)", default="0.1")
    if target == 0: print(col(C.RED, "  PB 不能为 0")); pause(); return
    # 展示用：目标净资产（显示值）= 显示价 × 显示股本 / 目标PB（与 core.set_target_pb 同公式）
    target_an = info.price_fact * info.volume_total / target
    print("  需要设置 AssetNet = " + str(int(round(target_an))))
    if not confirm("确认修改?", no=False): return
    # 转调 core: set_target_pb(InfoModel, 目标PB) 反推净资产并写入（同步 Prev，Min 归零）
    set_target_pb(info, target)
    e.modified = True
    print(col(C.GREEN, "  新 PB = " + str(round(calc_pb(info._d), 4))))
    pause()

def change_debt(e):
    s = need_stock(e)
    if not s: return
    info = s.info
    print("  当前负债率 = " + str(round(info.debt_ratio * 100, 2)) + "%")
    print("  负债率 = AssetLoan / (AssetLoan + AssetNet) * 100%")
    print("  负债率越低越安全, 0% 表示完全无负债")
    print("  负债率 = 1%: 极低,几乎无负债,非常安全")
    print("  负债率 = 30%: 正常,适度负债,风险可控")
    print("  负债率 = 70%: 较高,负债较多,风险较高")
    print()
    target = prompt_float("目标负债率 % (1=极低, 30=正常, 70=较高)", default="1.0", mn=0.01, mx=99.99)
    # 展示用：目标 AssetLoan（显示值）= AssetNet(显示) × target / (100-target)
    new_loan = info.asset_net * target / (100 - target)
    print("  需要设置 AssetLoan = " + str(int(round(new_loan))))
    if not confirm("确认修改?", no=False): return
    # 转调 core: set_target_debt_ratio(InfoModel, 目标百分数)
    set_target_debt_ratio(info, target)
    e.modified = True
    print(col(C.GREEN, "  新负债率 = " + str(round(info.debt_ratio * 100, 2)) + "%"))
    pause()

def change_pi(e):
    s = need_stock(e)
    if not s: return
    info = s.info
    print("  当前 PriceInit 发行价 = " + str(info.price_init_raw) + " (" + fmt_p(info.price_init_raw) + ")")
    print("  PriceInit 是涨跌停基准, 决定涨停/跌停价")
    print("  涨停 = PriceInit * (1 + RateLimit)")
    print("  跌停 = PriceInit * (1 - RateLimit)")
    print("  注意: PriceInit 是游戏内部值,显示价=PriceInit/100")
    print("  例如: PriceInit=80000 -> 显示价=800.00元")
    print()
    disp = prompt_float("新发行价 (Yuan, 显示价*100=内部值)", default=str(info.price_init_raw / 100), mn=0.01)
    rl = info.rate_limit
    raw = int(disp * 100)
    print("  新涨停价 = " + str(round(raw * (1 + rl))) + " (" + fmt_p(int(raw * (1 + rl))) + ")")
    print("  新跌停价 = " + str(round(raw * (1 - rl))) + " (" + fmt_p(int(raw * (1 - rl))) + ")")
    if not confirm("确认修改?", no=False): return
    # 转调 core: set_price_init(InfoModel, 显示元)
    set_price_init(info, disp)
    e.modified = True
    print(col(C.GREEN, "  新 limit_up=" + str(round(info.price_init_raw * (1 + rl))) + " limit_down=" + str(round(info.price_init_raw * (1 - rl)))))
    pause()

def change_pf(e):
    s = need_stock(e)
    if not s: return
    info = s.info
    print("  当前昨收/最新价 = " + str(info.last_close_raw) + " (" + fmt_p(info.last_close_raw) + ")")
    print("  (= 最后一根 K 线收盘价；PriceFact=" + str(info.price_fact_raw) + " 是陈旧参考值)")
    print("  注意: 显示价 = 内部值/100。例如 100000 -> 1000.00元")
    print()
    disp = prompt_float("新昨收/最新价 (Yuan, 显示价)", default=str(info.last_close), mn=0.01)
    if not confirm("确认修改?", no=False): return
    # 转调 core: set_price_fact_sync_candles(InfoModel, 显示元) —— K 线 OHLC 强制同步
    set_price_fact_sync_candles(info, disp)
    e.modified = True
    raw = info.price_fact_raw
    print(col(C.GREEN, "  设置为 " + str(raw) + " (" + fmt_p(raw) + ")，K线已强制同步！"))
    pause()

def change_rl(e):
    s = need_stock(e)
    if not s: return
    info = s.info
    print("  当前 RateLimit 涨跌幅 = " + str(round(info.rate_limit * 100, 1)) + "%")
    print("  涨停 = PriceInit * (1 + RateLimit)")
    print("  跌停 = PriceInit * (1 - RateLimit)")
    print("  值越大波动越剧烈, 值越小越稳定")
    print("  RateLimit = 5%: 小波动,股价变化慢")
    print("  RateLimit = 10%: 默认,正常波动")
    print("  RateLimit = 20%: 大幅波动,股价变化快")
    print()
    pct = prompt_float("新涨跌停幅度 % (10=10%%默认, 20=20%%大幅波动, 5=5%%小波动)", default="10", mn=0.1, mx=100)
    print("  新涨停价 = " + str(round(info.price_init_raw * (1 + pct / 100))) + " (" + fmt_p(int(info.price_init_raw * (1 + pct / 100))) + ")")
    print("  新跌停价 = " + str(round(info.price_init_raw * (1 - pct / 100))) + " (" + fmt_p(int(info.price_init_raw * (1 - pct / 100))) + ")")
    if not confirm("确认修改?", no=False): return
    # 转调 core: set_rate_limit(InfoModel, 百分数)
    set_rate_limit(info, pct)
    e.modified = True
    print(col(C.GREEN, "  新 RateLimit = " + str(pct) + "%"))
    pause()

def change_npc(e):
    s = need_stock(e)
    if not s: return
    inst, ret = s.institution, s.retail
    print(col(C.BOLD, "  当前:"))
    print("  主力可卖股数 Inst.VolSell=" + str(inst.volume_usable_sell_raw) + ", Inst.AmountBuy=" + str(inst.amount_usable_buy_raw))
    print("  散户可卖股数 Retail.VolSell=" + str(ret.volume_usable_sell_raw) + ", Retail.AmountBuy=" + str(ret.amount_usable_buy_raw))
    print()
    print("  1. 全部清零")
    print("     - 主力和散户都没有可卖的股票和可买的资金")
    print("     - 效果: 5档买卖盘全空,股票无法交易")
    print()
    print("  2. 中位数 (推荐)")
    print("     - 跟其他99只股票一样的正常水平")
    print("     - 效果: 5档有正常数量的挂单,交易正常进行")
    print()
    print("  3. 1.5倍中位")
    print("     - 比正常水平多50%的挂单")
    print("     - 效果: 5档挂单更密集,流动性更好")
    print()
    print("  4. 0.5倍交易缩量")
    print("     - 挂单数量减半,交易量缩小50%")
    print("     - 效果: 5档挂单更稀疏,流动性降低")
    print()
    print("  5. 自定义")
    print("     - 手动输入每个字段的值")
    print("     - 适合高级用户精确控制")
    print()
    mode = prompt_int("Mode", default=2, mn=1, mx=5)
    if mode in (2, 3, 4):
        # 转调 core: 取其它股票显示值中位 × mult，写回（setter 内部 ×100）
        mult = {2: 1.0, 3: 1.5, 4: 0.5}[mode]
        set_npc_quotes_by_median(e.model, s, mult)
    elif mode == 5:
        print()
        print("  === 参数说明 ===")
        print("  Inst.VolSell (主力可卖股数):")
        print("    - 主力机构当前持有多少股可以卖出")
        print("    - 值越大,卖单越多,股价越难涨")
        print("    - 值为0则主力没有货可卖")
        print()
        print("  Inst.AmountBuy (主力可买资金):")
        print("    - 主力机构有多少资金可以买入")
        print("    - 值越大,买单越多,股价越容易涨")
        print("    - 当前值: " + str(inst.amount_usable_buy_raw))
        print()
        print("  Retail.VolSell (散户可卖股数):")
        print("    - 散户当前持有多少股可以卖出")
        print("    - 值越大,卖单越多,股价越难涨")
        print("    - 值为-1表示无限制(游戏默认)")
        print()
        print("  Retail.AmountBuy (散户可买资金):")
        print("    - 散户有多少资金可以买入")
        print("    - 值越大,买单越多,股价越容易涨")
        print("    - 当前值: " + str(ret.amount_usable_buy_raw))
        print()
        print("  === 当前值 ===")
        print("  Inst.VolSell  = " + str(inst.volume_usable_sell_raw))
        print("  Inst.AmountBuy = " + str(inst.amount_usable_buy_raw))
        print("  Retail.VolSell  = " + str(ret.volume_usable_sell_raw))
        print("  Retail.AmountBuy = " + str(ret.amount_usable_buy_raw))
        print()
        # mode5 自定义：用户直接给定原始值（内部值），透传写入（与历史语义一致）
        inst._d["VolumeUsableSell"] = prompt_int("Inst.VolSell (主力可卖股数)", default=str(inst.volume_usable_sell_raw))
        inst._d["AmountUsableBuy"] = prompt_int("Inst.AmountBuy (主力可买资金)", default=str(inst.amount_usable_buy_raw))
        ret._d["VolumeUsableSell"] = prompt_int("Retail.VolSell (散户可卖股数)", default=str(ret.volume_usable_sell_raw))
        ret._d["AmountUsableBuy"] = prompt_int("Retail.AmountBuy (散户可买资金)", default=str(ret.amount_usable_buy_raw))
    elif mode == 1:
        # 转调 core: 清零主力/散户挂单（显示值 0，setter 写内部 0）
        clear_npc_quotes(inst, ret)
    e.modified = True
    print(col(C.GREEN, "  已更新"))
    pause()

def change_financials(e):
    """直接修改所有财务指标（自由设定数值）"""
    s = need_stock(e)
    if not s: return
    info = s.info._d   # 用户输入按内部值写入（与历史语义一致）；Prev/Min 同步见下
    
    clear()
    print(col(C.BOLD + C.CYAN, "="*70))
    print(col(C.BOLD + C.CYAN, "  自由设定财务指标 (Change Financials Freely)"))
    print(col(C.BOLD + C.CYAN, "="*70))
    
    print(col(C.BOLD, "\n  当前基础财务数据:"))
    print("  总股本 (VolumeTotal):      " + fmt_shares(info.get("VolumeTotal", 0)))
    print("  流通股 (VolumeFlow):       " + fmt_shares(info.get("VolumeFlow", 0)))
    print("  净资产 (AssetNet):         " + fmt_m(info.get("AssetNet", 0)))
    print("  总负债 (AssetLoan):        " + fmt_m(info.get("AssetLoan", 0)))
    print("  业务收益 (RewardBusiness): " + fmt_m(info.get("RewardBusiness", 0)))
    print("  其他收益 (RewardOther):    " + fmt_m(info.get("RewardOther", 0)))
    print("  业务成本 (CostBusiness):   " + fmt_m(info.get("CostBusiness", 0)))
    print("  其他成本 (CostOther):      " + fmt_m(info.get("CostOther", 0)))
    print()
    print(col(C.YELLOW, "  * 提示：支持输入 '1000000' 或 '100万' 或 '5亿'，程序会自动转换！"))
    print(col(C.YELLOW, "  * 直接按 Enter 保持原值不变。"))
    print(col(C.YELLOW, "  * 注意：股数/金额均为游戏内部值(显示值的100倍)。输入'100万'会写入内部值100万，"))
    print(col(C.YELLOW, "    对应游戏显示 1万 股。若要游戏显示 100万 股，请输入 '1亿'。"))
    print()
    
    def parse_input(prompt_text, current_value):
        default = current_value if current_value is not None else 0
        v = prompt(prompt_text, str(default)).strip()
        if not v or v == str(default):
            return default
        
        v = v.replace(',', '')
        try:
            if "万" in v:
                return int(float(v.replace("万", "")) * 10000)
            elif "亿" in v:
                return int(float(v.replace("亿", "")) * 100000000)
            return int(float(v))
        except:
            print(col(C.RED, "  无效输入，使用默认值"))
            return default

    info["VolumeTotal"] = parse_input("总股本 (VolumeTotal)", info.get("VolumeTotal"))
    info["VolumeFlow"] = parse_input("流通股 (VolumeFlow)", info.get("VolumeFlow"))
    info["AssetNet"] = parse_input("净资产 (AssetNet)", info.get("AssetNet"))
    info["AssetLoan"] = parse_input("总负债 (AssetLoan)", info.get("AssetLoan"))
    info["RewardBusiness"] = parse_input("业务收益 (RewardBusiness)", info.get("RewardBusiness"))
    info["RewardOther"] = parse_input("其他收益 (RewardOther)", info.get("RewardOther"))
    info["CostBusiness"] = parse_input("业务成本 (CostBusiness)", info.get("CostBusiness"))
    info["CostOther"] = parse_input("其他成本 (CostOther)", info.get("CostOther"))
    
    # 同步更新历史/最小值字段，防止游戏逻辑出错
    for k in ("AssetNetPrev", "AssetLoanPrev", "RewardBusinessPrev", "RewardOtherPrev", "CostBusinessPrev", "CostOtherPrev"):
        base_key = k.replace("Prev", "")
        if k in info and base_key in info:
            info[k] = info[base_key]
            
    for k in ("AssetNetMin", "AssetLoanMin", "RewardBusinessMin", "RewardOtherMin", "CostBusinessMin", "CostOtherMin"):
        if k in info:
            info[k] = 0

    if "ProfitNetPrev" in info:
        info["ProfitNetPrev"] = info["RewardBusiness"] + info["RewardOther"] - info["CostBusiness"] - info["CostOther"]

    e.modified = True
    print(col(C.GREEN, "\n  财务指标已全面更新！"))
    pause()

def change_ns(e):
    ns = e.model.notice_style
    print(col(C.BOLD, "  当前购买取向 NoticeStyle:"))
    for k, v in ns.items(): print("  " + k.ljust(30) + ": " + str(v))
    print()
    print("  1. 推高个股买入")
    print("     - NormalStockStrength 1->2: NPC买入个股的力度翻倍")
    print("     - NormalStockCreateProb 0->0.5: NPC有50%概率主动建仓个股")
    print("     - 效果: 个股股价更容易上涨")
    print()
    print("  2. 推高板块买入")
    print("     - NormalSectorStrength 1->1.5: NPC买入板块的力度增加50%")
    print("     - 效果: 板块内所有股票都会受益,但不如个股明显")
    print()
    print("  3. 让所有板块下跌")
    print("     - NormalSectorStrength 1->0.5: NPC买入板块的力度减半")
    print("     - NormalSectorCreateProb 0->0: NPC不主动建仓板块")
    print("     - 效果: 板块内所有股票都会下跌")
    print()
    print("  4. 让所有个股下跌")
    print("     - NormalStockStrength 1->0.5: NPC买入个股的力度减半")
    print("     - NormalStockCreateProb 0->0: NPC不主动建仓个股")
    print("     - 效果: 所有个股股价更容易下跌")
    print()
    print("  5. 全部复原")
    print("     - Strength=1.0, CreateProb=0.0: 恢复游戏默认值")
    print("     - 效果: NPC行为恢复正常,不会特别推高或拉低任何股票")
    print()
    print("  6. 自定义")
    print("     - 手动输入每个参数的值")
    print("     - 适合高级用户精确控制NPC行为")
    print()
    m = prompt_int("Mode", default=1, mn=1, mx=6)
    # mode 1-5 转调 core.apply_notice_style（预设模式写 ns 个股/板块/市场参数）
    if m in (1, 2, 3, 4, 5):
        apply_notice_style(ns, m)
        print({1: "  已推高个股买入力度", 2: "  已推高板块买入力度", 3: "  已设置板块下跌",
               4: "  已设置个股下跌", 5: "  已全部复原"}[m])
    elif m == 6:
        print("  当前值 -> 手动输入新值 (直接回车保持不变)")
        for k in list(ns.keys()):
            if k in ("RankCreateExchangeRate", "ReportCreateDay"):
                ns[k] = prompt_int("  " + k + " = " + str(ns[k]) + " ->", default=str(ns[k]))
            else:
                ns[k] = prompt_float("  " + k + " = " + str(ns[k]) + " ->", default=str(ns[k]))
    e.modified = True
    pause()

# ====== 【核心新增】智能增发扩股函数 (维持估值与股价不变) ======
def dilute_stock_for_shortage(stock, shortage):
    """定向增发：同比例扩大总股本/流通股+财务指标，维持 PE/PB 不变。

    stock: 裸 stock dict 或 StockModel。shortage: **内部值**缺口（TUI 历史语义，
    与 change_player 的内部值链路一致）。转调 core.dilute_for_shortage（收 StockModel
    + 显示股 shortage），内部做单位适配。
    """
    from src.core.savemodel import StockModel as _SM
    sm = stock if isinstance(stock, _SM) else _SM(stock)
    old_total = sm.info.volume_total_raw
    if old_total <= 0: old_total = 1
    # shortage 是内部值 → 转显示股传 core
    shortage_display = shortage / SHARE_SCALE
    print(col(C.YELLOW, f"  ⚠️ 筹码不足，触发定向增发机制！"))
    print(col(C.YELLOW, f"  增发数量: {shortage:,} 股 | 扩容比例: {(old_total + shortage) / old_total:.4f} 倍"))
    dilute_for_shortage(sm, shortage_display)

# ====== 【核心升级】玩家持仓修改 (带全局筹码视野与NPC同步过户及智能增发) ======
def change_player(e):
    print(col(C.BOLD, "  当前玩家持仓 Player.StockPos:"))
    sp = e.model.player._d["StockPos"]
    if not sp: print("    (空)")
    for i, p in enumerate(sp): print("  [" + str(i) + "] Code=" + str(p.get("Code")) + " Amount=" + str(p.get("Amount")) + " Vol=" + str(p.get("VolumeUsable")))
    print()
    print("  1. 添加新持仓")
    print("     - 输入股票代码、盈亏金额、可用股数")
    print("     - 适合开新仓或加仓")
    print()
    print("  2. 修改指定Code的持仓")
    print("     - 修改某只股票的盈亏金额和可用股数")
    print("     - 适合调整仓位或止盈止损")
    print()
    print("  3. 删除指定Code的持仓")
    print("     - 删除某只股票的持仓记录")
    print("     - 适合清仓或止损")
    print()
    print("  4. 修改Player总资金")
    print("     - 修改你的总盈亏金额")
    print("     - 适合调整总资产")
    print()
    m = prompt_int("Mode", default=2, mn=1, mx=4)
    
    if m in (1, 2, 3):
        c = prompt_int("Code (支持X1020格式)", mn=1000, mx=9999, extract_code=True)
        stock = e.find(c)
        if not stock:
            print(col(C.RED, "  找不到 Stock X" + str(c))); pause(); return
            
        info = stock.info._d
        inst = stock.institution._d
        ret = stock.retail._d
        hot = stock.hot_money._d if stock.hot_money is not None else {}
        
        # 1. 显示全局筹码视野
        hr("-", 50)
        print(col(C.BOLD + C.CYAN, "  [X" + str(c) + " 筹码分布全景]"))
        print("  总股本 (VolumeTotal): " + col(C.YELLOW, fmt_shares(info.get("VolumeTotal", 0))))
        print("  流通股 (VolumeFlow):  " + col(C.YELLOW, fmt_shares(info.get("VolumeFlow", 0))))
        print()
        print("  机构可卖 (Inst.VolSell):   " + str(inst.get("VolumeUsableSell", 0)))
        print("  散户可卖 (Retail.VolSell): " + str(ret.get("VolumeUsableSell", 0)))
        if hot: print("  游资可卖 (HotMoney.VolSell): " + str(hot.get("VolumeUsableSell", 0)))
        hr("-", 50)
        
        old_vol = 0
        new_vol = 0
        if m == 1:
            a = prompt_int("Amount (盈亏, 正=赚, 负=亏, 0=刚开仓)", default=0)
            v = prompt_int("VolumeUsable (玩家新增可用股数)", default=0)
            sp.append({"Code":c, "Amount":a, "VolumeUsable":v})
            old_vol = 0
            new_vol = v
        elif m == 2:
            found = False
            for p in sp:
                if p.get("Code") == c:
                    old_vol = p.get("VolumeUsable", 0)
                    print("  当前玩家持仓: " + str(old_vol) + " 股")
                    p["Amount"] = prompt_int("Amount (盈亏)", default=str(p.get("Amount",0)))
                    new_vol = prompt_int("VolumeUsable (玩家修改后可用股数)", default=str(old_vol))
                    p["VolumeUsable"] = new_vol
                    found = True
                    break
            if not found: 
                print(col(C.RED, "  找不到 Code=" + str(c))); pause(); return
        elif m == 3:
            found = False
            for p in sp:
                if p.get("Code") == c:
                    old_vol = p.get("VolumeUsable", 0)
                    found = True
                    break
            if not found:
                print(col(C.RED, "  找不到 Code=" + str(c))); pause(); return
            e.data["Player"]["StockPos"] = [p for p in sp if p.get("Code") != c]
            new_vol = 0
            print(col(C.GREEN, "  玩家持仓已删除"))
            
        # 2. 计算差值并同步NPC持仓 (筹码守恒与智能增发)
        delta = new_vol - old_vol
        if delta != 0:
            print()
            if delta > 0:
                print(col(C.YELLOW, "  ⚠️ 玩家加仓了 " + str(delta) + " 股。"))
                print("  这些股票必须从NPC手里买过来，请选择从谁手里扣减可卖股数：")
            else:
                print(col(C.YELLOW, "  ⚠️ 玩家减仓了 " + str(abs(delta)) + " 股。"))
                print("  这些股票卖给了NPC，请选择把股票过户给谁（增加其可卖股数）：")
                
            print("  1. 机构 (Institution)")
            print("  2. 散户 (Retail)")
            if hot: print("  3. 游资 (HotMoney)")
            print("  0. 不同步 (凭空生成/销毁，不推荐)")
            
            max_opt = 3 if hot else 2
            target = prompt_int("选择过户对象", default=1, mn=0, mx=max_opt)
            
            if target == 0:
                print(col(C.YELLOW, "  已跳过NPC同步 (筹码不守恒，可能影响游戏内交易逻辑)"))
            else:
                npc_dict = {}
                npc_name = ""
                if target == 1: npc_dict, npc_name = inst, "机构"
                elif target == 2: npc_dict, npc_name = ret, "散户"
                elif target == 3 and hot: npc_dict, npc_name = hot, "游资"
                
                cur_npc_vol = npc_dict.get("VolumeUsableSell", 0)
                
                if delta > 0: # 玩家买入，NPC减少
                    if cur_npc_vol == -1:
                        print(col(C.YELLOW, f"  {npc_name}可卖为-1(无限制)，无需扣减，无需增发。"))
                    else:
                        shortage = delta - cur_npc_vol
                        if shortage > 0:
                            # 触发增发！
                            dilute_stock_for_shortage(stock, shortage)
                            npc_dict["VolumeUsableSell"] = 0
                            print(col(C.GREEN, f"  {npc_name}可卖已扣减至0，剩余缺口已通过增发补齐！"))
                        else:
                            npc_dict["VolumeUsableSell"] = cur_npc_vol - delta
                            print(col(C.GREEN, f"  {npc_name}可卖已同步扣减为: " + str(npc_dict["VolumeUsableSell"])))
                            
                else: # 玩家卖出(delta < 0)，NPC增加
                    if cur_npc_vol == -1:
                        print(col(C.YELLOW, f"  {npc_name}可卖为-1(无限制)，无需增加。"))
                    else:
                        npc_dict["VolumeUsableSell"] = cur_npc_vol + abs(delta)
                        print(col(C.GREEN, f"  {npc_name}可卖已同步增加为: " + str(npc_dict["VolumeUsableSell"])))
                
    elif m == 4:
        e.data["Player"]["Amount"] = prompt_int("New Player.Amount (总盈亏)", default=str(e.data["Player"].get("Amount",0)))
        
    e.modified = True
    print(col(C.GREEN, "  玩家数据已更新"))
    pause()

def clean_ng(e):
    ng = e.data["Market"].get("NoticeGroup", {})
    if isinstance(ng, list):
        total = len(ng)
        print("  NoticeGroup (list): " + str(total) + " 条")
        if total == 0: print(col(C.YELLOW, "  已经是空的")); pause(); return
        if not confirm("清空所有 " + str(total) + " 条?", no=False): return
        e.data["Market"]["NoticeGroup"] = []
        e.modified = True
        print(col(C.GREEN, "  已清空")); pause(); return
    sizes = {k: len(v) if isinstance(v, list) else 0 for k, v in ng.items()}
    total = sum(sizes.values())
    print("  NoticeGroup: " + str(sizes))
    if total == 0: print(col(C.YELLOW, "  已经是空的")); pause(); return
    if not confirm("清空所有 " + str(total) + " 条?", no=False): return
    for k in ng: ng[k] = []
    e.modified = True
    print(col(C.GREEN, "  已清空"))
    pause()

def trim_hn(e):
    hn = e.data["Market"].get("HuddleNpc", [])
    before = sum(len(h.get("StockPos", [])) for h in hn)
    print("  HuddleNpc: " + str(len(hn)) + " 个NPC, " + str(before) + " 条持仓")
    keep = prompt_int("每个NPC保留几条持仓 (0=全部清空, 10=推荐)", default=10, mn=0, mx=200)
    if not confirm("砍到每个NPC " + str(keep) + " 条?", no=False): return
    for h in hn:
        sp = h.get("StockPos", [])
        if len(sp) > keep: h["StockPos"] = sp[:keep]
    after = sum(len(h.get("StockPos", [])) for h in hn)
    e.modified = True
    print(col(C.GREEN, "  " + str(before) + " -> " + str(after) + " 条"))
    pause()

def clean_tt(e):
    tt = e.data["Player"].get("TradeType", [])
    print("  TradeType: " + str(len(tt)) + " 条记录")
    if not tt: print(col(C.YELLOW, "  已经是空的")); pause(); return
    if not confirm("清空?", no=False): return
    e.data["Player"]["TradeType"] = []
    e.modified = True
    print(col(C.GREEN, "  已清空"))
    pause()

# ====== 单个股票操作菜单 ======
def stock_menu(e, code):
    """单个股票操作菜单"""
    e.selected_code = code
    while True:
        clear()
        stock = e.find(code)
        if not stock:
            print(col(C.RED, "  Stock X" + str(code) + " not found!"))
            pause()
            return
        info = stock.info._d
        np_ = info["RewardBusiness"]+info["RewardOther"]-info["CostBusiness"]-info["CostOther"]
        pe = calc_pe(info)
        pb = calc_pb(info)
        dr = info["AssetLoan"]/(info["AssetLoan"]+info["AssetNet"])*100 if (info["AssetLoan"]+info["AssetNet"]) else 0
        
        print(col(C.BOLD + C.CYAN, "="*70))
        print(col(C.BOLD + C.CYAN, "  Stock X" + str(code) + " Operations"))
        print(col(C.BOLD + C.CYAN, "="*70))
        print("  PriceInit 发行价:    " + fmt_p(info["PriceInit"]))
        print("  昨收/最新价:    " + fmt_p(last_close_raw(info)) + "  (PriceFact=" + fmt_p(info["PriceFact"]) + " 陈旧)")
        print("  RateLimit 涨跌幅:    " + str(round(info["RateLimit"]*100, 1)) + "%")
        if pe != float("inf"): print("  PE 市盈率:           " + str(round(pe, 4)))
        else: print("  PE 市盈率:           N/A (净利润<=0)")
        if pb != float("inf"): print("  PB 市净率:           " + str(round(pb, 4)))
        else: print("  PB 市净率:           N/A")
        print("  DebtRatio 负债率:    " + str(round(dr, 2)) + "%")
        if e.modified: print(col(C.YELLOW, "  * UNSAVED *"))
        print()
        print("  1.  Show full details      -- 查看完整详情")
        print("  2.  Change PE              -- 改市盈率")
        print("  3.  Change PB              -- 改市净率")
        print("  4.  Change debt ratio      -- 改负债率")
        print("  5.  Change PriceInit       -- 改发行价 (基准价)")
        print("  6.  Change PriceFact       -- 改昨收/开盘价 (带K线同步)")
        print("  7.  Change RateLimit       -- 改涨跌停幅度")
        print("  8.  Change NPC quotes      -- 改主力/散户挂单数量")
        print("  9.  Change financials      -- 自由设定所有财务指标 (防回滚)")
        print("  --- Notices & corporate actions 公告/公司行动 ---")
        print("  10. View notices           -- 查看该股的公告/业绩报告")
        print("  11. Publish notice         -- 为该股发布公告/业绩报告")
        print("  12. Stock dividend         -- 该股分红 (现金/送股/先送后现)")
        print("  13. Private placement      -- 该股定向增发")
        print("  0.  Back to main menu      -- 返回主菜单")
        print()
        ch = prompt("Choose", "1")
        if not ch.isdigit(): continue
        ch = int(ch)

        if ch == 1: print(format_stock_detail(stock, code)); pause()
        elif ch == 2: change_pe(e)
        elif ch == 3: change_pb(e)
        elif ch == 4: change_debt(e)
        elif ch == 5: change_pi(e)
        elif ch == 6: change_pf(e)
        elif ch == 7: change_rl(e)
        elif ch == 8: change_npc(e)
        elif ch == 9: change_financials(e)
        elif ch == 10: view_notices(e, code)
        elif ch == 11: publish_notice(e, default_code=code)
        elif ch == 12: stock_dividend_for_code(e, code)
        elif ch == 13: private_placement_for_code(e, code)
        elif ch == 0: return

def show_all_stocks(e):
    """显示所有股票列表"""
    codes = e.codes()
    print(col(C.BOLD, "  All stocks (" + str(len(codes)) + " total):"))
    print()
    for i in range(0, len(codes), 5):
        line = ""
        for j in range(5):
            if i+j < len(codes):
                c = codes[i+j]
                stock = e.find(c)
                price = stock.info.last_close
                line += "  X" + str(c).zfill(4) + ": " + str(round(price, 2)).rjust(10) + " Yuan"
        print(line)

# ====== 公告/退市/增发/分红/市场整顿 等扩展功能 (社区贡献 extra 功能) ======

# [extra] 社区贡献 extra 功能（公告/退市/增发/分红等），非原主干
def get_current_game_day(stock):
    """
    获取股票的当前游戏天数
    
    从K线数据中获取最后一根K线的Day值作为当前游戏天数。
    如果没有K线数据，则返回0。
    
    参数:
        stock: 股票数据字典
    
    返回:
        int: 当前游戏天数
    """
    info = stock.info._d
    candles = info.get("Candles", [])
    if candles:
        return candles[-1].get("Day", 0)
    return 0


# [extra] 社区贡献 extra 功能（公告/退市/增发/分红等），非原主干
def get_or_create_delisted_pool(e):
    
    if "DelistedPool" not in e.data["Market"] or not isinstance(e.data["Market"]["DelistedPool"], dict):
        e.data["Market"]["DelistedPool"] = {"A": [], "B": []}
    pool = e.data["Market"]["DelistedPool"]
    if "A" not in pool or not isinstance(pool["A"], list):
        pool["A"] = []
    if "B" not in pool or not isinstance(pool["B"], list):
        pool["B"] = []
    return pool


# [extra] 社区贡献 extra 功能（公告/退市/增发/分红等），非原主干
def _build_stock_notice(code, stock, notice_day, star, strength=1.0, create_prob=0.08):
    """
    构建单条股票公告 (NoticeNormal) 数据对象（不写入存档）
    
    新公式:
      Prob = Star * strength   (strength=NormalStockStrength/NormalSectorStrength/NormalMarketStrength)
      ReduceProb = create_prob / Star   (create_prob=NormalStockCreateProb/NormalSectorCreateProb/NormalMarketCreateProb)
    
    参数:
        code: 股票代码
        stock: 股票数据字典
        notice_day: 公告发布时间
        star: 星级
        strength: 对应的 Normal*Strength
        create_prob: 对应的 Normal*CreateProb
    
    返回:
        dict: 构建好的公告对象
    """
    prob = star * strength
    reduce_prob = create_prob / star if star > 0 else 0
    
    return {
        "Code": code,
        "Buy": True,
        "Star": star,
        "ReduceProb": reduce_prob,
        "Prob": prob,
        "Day": notice_day,
        "_strength": strength,
        "_create_prob": create_prob
    }


# [extra] 社区贡献 extra 功能（公告/退市/增发/分红等），非原主干
def _print_notice_preview(n, label="公告"):
    
    buy_text = col(C.RED, "True (利好)") if n.get("Buy", False) else col(C.GREEN, "False (利空)")
    print("      Code:       X" + str(n["Code"]))
    print("      Buy:        " + buy_text)
    print("      Star:       " + str(n["Star"]))
    print("      ReduceProb: " + str(round(n["ReduceProb"], 6)))
    print("      Prob:       " + str(round(n["Prob"], 6)))
    s = n.get("_strength", 0)
    cp = n.get("_create_prob", 0)
    print("                  Prob = Star(" + str(n["Star"]) + ") × Strength(" + str(round(s, 4)) + ") = " + str(round(n["Prob"], 4)))
    print("                  ReduceProb = CreateProb(" + str(round(cp, 4)) + ") / Star(" + str(n["Star"]) + ") = " + str(round(n["ReduceProb"], 6)))
    print("      Day:        Day " + str(n["Day"]))


# [extra] 社区贡献 extra 功能（公告/退市/增发/分红等），非原主干
def _append_notice_normal(e, notice_list):
    """
    将一批 NoticeNormal 公告写入存档的 NoticeGroup.NoticeNormal
    
    参数:
        e: Editor 实例
        notice_list: 公告对象列表
    """
    ng = e.data["Market"].get("NoticeGroup", {})
    if not isinstance(ng, dict):
        ng = {}
        e.data["Market"]["NoticeGroup"] = ng
    
    for key in ("NoticeNormal", "NoticeRank", "NoticeReport"):
        if key not in ng:
            ng[key] = []
    
    for n in notice_list:
        # 移除构建时临时字段
        nn = {k: v for k, v in n.items() if not k.startswith("_")}
        ng["NoticeNormal"].append(nn)
    
    e.modified = True
    print(col(C.GREEN, "  发布成功! 共 " + str(len(notice_list)) + " 条已添加到 NoticeGroup.NoticeNormal"))
    pause()


# [extra] 社区贡献 extra 功能（公告/退市/增发/分红等），非原主干
def _filter_delisted_candidates(e):
    
    ng = e.data["Market"].get("NoticeGroup", {})
    reports = ng.get("NoticeReport", []) if isinstance(ng, dict) else []
    by_code = {}
    for r in reports:
        c = r.get("Code")
        if c is None: continue
        by_code.setdefault(c, []).append(r)
    
    candidates = []
    for s in e.stocks():
        info = s.info._d
        code = info.get("Code")
        asset_net = info.get("AssetNet", 0)
        asset_loan = info.get("AssetLoan", 0)
        total = asset_net + asset_loan
        dr = (asset_loan / total * 100) if total > 0 else 0
        if dr <= 80:
            continue
        rs = by_code.get(code, [])
        if not rs:
            continue
        rs_sorted = sorted(rs, key=lambda x: x.get("Day", 0), reverse=True)
        recent = rs_sorted[:5]
        if len(recent) < 5:
            continue
        all_neg = True
        for r in recent:
            nb = r.get("RewardBusiness", 0) + r.get("RewardOther", 0) - r.get("CostBusiness", 0) - r.get("CostOther", 0)
            if nb >= 0:
                all_neg = False
                break
        if all_neg:
            candidates.append((code, dr, len(recent)))
    return candidates


# [extra] 社区贡献 extra 功能（公告/退市/增发/分红等），非原主干
def change_npc_all_to_retail(e):
    """
    砍机构持仓（全市场）: 遍历所有股票，将所有NPC的该股票持仓清空，合计后转入散户持仓。
    
    参数:
        e (Editor): Editor 实例
    返回: None
    异常: 无
    作者: 琛ccsy
    """
    print()
    print("  说明: 将扫描所有NPC的所有股票持仓，合计后转入对应股票的散户持仓")
    print("        会清空 AloneNpc/HuddleNpc/MessageNpc/RelayNpc/SneakNpc 的全部持仓")
    # 转调 core: collect_npc_holdings 扫描汇总（不改动），打印明细 + confirm 后再 move_npc_to_retail 执行
    removed = collect_npc_holdings(e.model)
    if not removed:
        print(col(C.GREEN, "  所有 NPC 无持仓可砍"))
        pause()
        return
    print(col(C.BOLD, "  砍机构明细:"))
    for c, v in removed.items():
        print("  X" + str(c) + ": " + str(v) + " 手 -> Retail.VolSell")
    if not confirm("确认执行?", no=False):
        print(col(C.DIM, "  已取消")); pause(); return
    # 转调 core: move_npc_to_retail(SaveModel, holdings) 转散户 + 筹码守恒平账
    move_npc_to_retail(e.model, removed)
    e.modified = True
    print(col(C.GREEN, "  砍机构完成, 合计 " + str(sum(removed.values())) + " 手已转入散户"))
    pause()


# [extra] 社区贡献 extra 功能（公告/退市/增发/分红等），非原主干
def market_rectification(e):
    """
    市场整顿: 按账户持仓比例修正使 sum_hold == VolumeFlow
    
    参数:
        e (Editor): Editor 实例
    返回: None
    作者: 琛ccsy
    """
    print()
    print("  市场整顿说明 (逐只股票核对 sum_hold == VolumeFlow):")
    print("    1) 差异较小 (<10000 手): 按「散户 → 主力 → NPC(5类) → 玩家」顺序依次扣减")
    print("       若缺口仍存在, 最后扣玩家持仓")
    print("    2) 差异较大 (≥10000 手): 按比例缩放所有账户持仓 (保持相对比例)")
    print("    3) 差异为负 (持仓 < 流通股): 差额全部加回主力持仓")
    print("    4) 兜底: 若处理后仍不平衡, 直接修改 VolumeFlow 使账面上平衡")
    print()
    print("  账户范围: 玩家 + 主力(Institution) + 散户(Retail) + AloneNpc/HuddleNpc/MessageNpc/RelayNpc/SneakNpc")
    print()
    # 转调 core: rectify_market(SaveModel) 强制筹码守恒，返回 {code: 说明}
    summary = rectify_market(e.model)
    e.modified = True
    print(col(C.BOLD, "  === 市场整顿明细 ==="))
    for c, r in summary.items():
        print("  X" + str(c) + ": " + str(r))
    print(col(C.GREEN, "  市场整顿完成"))
    pause()


# [extra] 社区贡献 extra 功能（公告/退市/增发/分红等），非原主干
def show_notice_detail(notice):
    """
    显示单条股票公告 (NoticeNormal) 的详细信息
    """
    hr()
    print(col(C.BOLD, "  股票公告详情 (NoticeNormal)"))
    hr()
    buy_text = col(C.RED, "利好 (Buy=True)") if notice.get("Buy", False) else col(C.GREEN, "利空 (Buy=False)")
    star = notice.get("Star", 0)
    print("  Code 股票代码:      X" + str(notice.get("Code", 0)))
    print("  Type 类型:          " + buy_text)
    print("  Star 星级:          " + str(star) + " 星 (" + col(C.YELLOW, "★" * star + "☆" * (5 - star)) + ")")
    print("  ReduceProb 衰减系数: " + str(round(notice.get("ReduceProb", 0), 6)))
    print("  Prob 影响强度:       " + str(round(notice.get("Prob", 0), 4)))
    print("  Day 发布时间:       Day " + str(notice.get("Day", 0)))
    hr()
    
    prob = notice.get("Prob", 0)
    print("  效果说明:")
    if notice.get("Buy", False):
        print("    - AI买入动力增强")
        print("    - 股价有上涨趋势")
    else:
        print("    - AI卖出动力增强")
        print("    - 股价有下跌趋势")
    print("    - 影响持续约 " + str(notice.get("Day", 0)) + " 天")
    print()
    print("  计算公式: Prob = Star × Strength   ReduceProb = CreateProb / Star")
    print("    Prob = " + str(star) + " × ? = " + str(round(prob, 4)))
    print("    ReduceProb = CreateProb / " + str(star) + " = " + str(round(notice.get("ReduceProb", 0), 6)))
    print("    Day = Day " + str(notice.get("Day", 0)))
    hr()


# [extra] 社区贡献 extra 功能（公告/退市/增发/分红等），非原主干
def show_report_detail(report, stock=None):
    """
    显示单条业绩报告的详细信息
    
    参数:
        report: 业绩报告字典，包含 Code, Buy, Star, ReduceProb, Prob, Day 及财务字段
        stock: 可选，当前股票数据字典，用于显示实时数据对比
    
    返回:
        无
    """
    hr()
    print(col(C.BOLD, "  业绩报告详情"))
    hr()
    buy_text = col(C.RED, "利好 (Buy=True)") if report.get("Buy", False) else col(C.GREEN, "利空 (Buy=False)")
    star = report.get("Star", 0)
    print("  Code 股票代码:      X" + str(report.get("Code", 0)))
    print("  Type 类型:          " + buy_text)
    print("  Star 星级:          " + str(star) + " 星 (" + col(C.YELLOW, "★" * star + "☆" * (5 - star)) + ")")
    print("  ReduceProb 衰减系数: " + str(round(report.get("ReduceProb", 0), 6)))
    print("  Prob 影响强度:       " + str(round(report.get("Prob", 0), 4)))
    print("  Day 发布时间:       Day " + str(report.get("Day", 0)))
    hr()
    
    prob = report.get("Prob", 0)
    day = report.get("Day", 0)
    print("  效果说明:")
    if report.get("Buy", False):
        print("    - AI买入动力 " + ("增强" if prob < 0 else "减弱"))
        print("    - 股价有" + ("上涨" if prob < 0 else "下跌") + "趋势")
    else:
        print("    - AI卖出动力 " + ("增强" if prob > 0 else "减弱"))
        print("    - 股价有" + ("下跌" if prob > 0 else "上涨") + "趋势")
    print("    - 影响持续约 " + str(day) + " 天")
    print()
    print("  计算公式: Prob = Star × ReportStrength   ReduceProb = 1 / Star")
    print("    Prob = " + str(star) + " × ReportStrength = " + str(round(prob, 4)))
    print("    ReduceProb = 1 / " + str(star) + " = " + str(round(report.get("ReduceProb", 0), 6)))
    print("    Day = Day " + str(day))
    hr()
    
    # 财务数据变化率分析
    prev_fields = [
        ("AssetNet", "净资产"),
        ("AssetLoan", "总负债"),
        ("RewardBusiness", "业务收益"),
        ("RewardOther", "其他收益"),
        ("CostBusiness", "业务成本"),
        ("CostOther", "其他成本"),
    ]
    print(col(C.BOLD, "  财务数据变化率 (现数据/原数据 - 1):"))
    print("  " + "指标".ljust(10) + " " + "原数据".rjust(14) + " " + "新数据".rjust(14) + " " + "变化率".rjust(12))
    print("  " + "-" * 60)
    for key, label in prev_fields:
        prev = report.get(key + "Prev", 0)
        curr = report.get(key, 0)
        if prev and prev != 0:
            change_rate = (curr / prev - 1) * 100
            rate_text = ("+" if change_rate > 0 else "") + str(round(change_rate, 2)) + "%"
            if change_rate > 0:
                rate_color = C.GREEN
            elif change_rate < 0:
                rate_color = C.RED
            else:
                rate_color = C.RESET
        else:
            rate_text = "N/A"
            rate_color = C.DIM
        print("  " + label.ljust(12) + " " + str(prev).rjust(16) + " " + str(curr).rjust(16) + " " + col(rate_color, rate_text.rjust(12)))
    print()
    # 计算净利润变化
    prev_profit = (report.get("RewardBusinessPrev", 0) + report.get("RewardOtherPrev", 0)
                   - report.get("CostBusinessPrev", 0) - report.get("CostOtherPrev", 0))
    curr_profit = (report.get("RewardBusiness", 0) + report.get("RewardOther", 0)
                   - report.get("CostBusiness", 0) - report.get("CostOther", 0))
    if prev_profit and prev_profit != 0:
        profit_change = (curr_profit / prev_profit - 1) * 100
        print("  净利润变化率: " + ("+" if profit_change > 0 else "") + str(round(profit_change, 2)) + "%")
    else:
        print("  原净利润: " + str(prev_profit) + "  新净利润: " + str(curr_profit))
    
    

# [extra] 社区贡献 extra 功能（公告/退市/增发/分红等），非原主干
def _create_stock_performance(e, code, stock, notice_day, use_change_rate=False):
    """
    创建股票业绩 (NoticeReport)
    
    用户选择星级，系统自动计算Prob值:
    新公式:
      Prob = Star * ReportStrength   (ReportStrength = NoticeStyle.ReportStrength)
      ReduceProb = 1 / Star
    
    输入模式:
      - use_change_rate=True: 主菜单入口，仅输入变化率 x%，新数据=原数据×(1 + x%/100)
      - use_change_rate=False: 个股菜单入口，保持原绝对值输入
    
    参数:
        e: Editor 编辑器实例
        code: 股票代码
        stock: 股票数据字典
        notice_day: 公告发布天数 (当前游戏天数+1)
        use_change_rate: 是否使用变化率输入模式
    
    返回:
        无
    """
    info = stock.info._d
    ns = e.data["Market"].get("NoticeStyle", {})
    report_strength = float(ns.get("ReportStrength", 1.0))
    
    print()
    print("  === 股票业绩 (NoticeReport) ===")
    print("  ReportStrength: " + str(round(report_strength, 4)))
    print()
    
    star = prompt_int("Star 星级 (0-5)", default=3, mn=0, mx=5)
    
    prob = star * report_strength
    reduce_prob = (1.0 / star) if star > 0 else 0
    
    print()
    print("  Prob = Star(" + str(star) + ") × ReportStrength(" + str(round(report_strength, 4)) + ") = " + str(round(prob, 4)))
    print("  ReduceProb = 1 / Star(" + str(star) + ") = " + str(round(reduce_prob, 6)))
    print()
    
    is_buy = prompt_int("Type 类型 (1=利好, 2=利空)", default=1, mn=1, mx=2) == 1
    
    # 字段配置: (键名, 中文名, 类型)
    fields = [
        ("AssetNet", "净资产", "int"),
        ("AssetLoan", "总负债", "int"),
        ("RewardBusiness", "业务收益", "int"),
        ("RewardOther", "其他收益", "int"),
        ("CostBusiness", "业务成本", "int"),
        ("CostOther", "其他成本", "int"),
    ]
    
    if use_change_rate:
        # 主菜单模式: 只输入变化率x%(百分比), 新数据 = 原数据 × (1 + x%/100)
        print(col(C.BOLD, "  当前原数据:"))
        for key, label, _ in fields:
            old_val = info.get(key, 0)
            print("    " + label.ljust(12) + ": " + str(old_val))
        print()
        print(col(C.BOLD, "  请输入变化率 x% (新数据 = 原数据 × (1 + x%/100))"))
        print("    例如: 10 表示 +10%,  -3.4 表示 -3.4%,  0 表示不变")
        print()
        new_values = {}
        for key, label, ftype in fields:
            old_val = info.get(key, 0)
            x_percent = prompt_float("  " + label + " 变化率 x% (原=" + str(old_val) + ")", default="0")
            x = x_percent / 100.0
            new_val = int(round(old_val * (1 + x)))
            new_values[key] = new_val
            rate_display = ("+" if x_percent > 0 else "") + str(x_percent) + "%"
            print("    → " + label.ljust(12) + ": " + str(old_val) + " → " + str(new_val) + "  (" + rate_display + ")")
        asset_net = new_values["AssetNet"]
        asset_loan = new_values["AssetLoan"]
        reward_business = new_values["RewardBusiness"]
        reward_other = new_values["RewardOther"]
        cost_business = new_values["CostBusiness"]
        cost_other = new_values["CostOther"]
    else:
        # 个股菜单模式: 原绝对值输入
        asset_net = prompt_int("AssetNet 净资产 (当前)", default=str(info.get("AssetNet", 0)))
        asset_loan = prompt_int("AssetLoan 总负债 (当前)", default=str(info.get("AssetLoan", 0)))
        reward_business = prompt_int("RewardBusiness 业务收益 (当前)", default=str(info.get("RewardBusiness", 0)))
        reward_other = prompt_int("RewardOther 其他收益 (当前)", default=str(info.get("RewardOther", 0)))
        cost_business = prompt_int("CostBusiness 业务成本 (当前)", default=str(info.get("CostBusiness", 0)))
        cost_other = prompt_int("CostOther 其他成本 (当前)", default=str(info.get("CostOther", 0)))
    
    notice = {
        "Code": code,
        "Buy": is_buy,
        "Star": star,
        "ReduceProb": reduce_prob,
        "Prob": prob,
        "Day": notice_day,
        "AssetNetPrev": info.get("AssetNet", 0),
        "AssetNet": asset_net,
        "AssetLoanPrev": info.get("AssetLoan", 0),
        "AssetLoan": asset_loan,
        "RewardBusinessPrev": info.get("RewardBusiness", 0),
        "RewardBusiness": reward_business,
        "RewardOtherPrev": info.get("RewardOther", 0),
        "RewardOther": reward_other,
        "CostBusinessPrev": info.get("CostBusiness", 0),
        "CostBusiness": cost_business,
        "CostOtherPrev": info.get("CostOther", 0),
        "CostOther": cost_other
    }
    
    print()
    print("  === 即将发布的股票业绩 ===")
    print("  Code 股票代码:      X" + str(code))
    print("  Buy 类型:            " + ("利好" if is_buy else "利空"))
    print("  Star 星级:          " + str(star) + " 星")
    print("  ReduceProb 衰减系数: " + str(round(reduce_prob, 4)))
    print("  Prob 影响强度:       " + str(round(prob, 4)))
    print("    Prob = Star(" + str(star) + ") × ReportStrength(" + str(round(report_strength, 4)) + ") = " + str(round(prob, 4)))
    print("    ReduceProb = 1 / Star(" + str(star) + ") = " + str(round(reduce_prob, 6)))
    print("  Day 发布时间:       Day " + str(notice_day))
    print()
    print("  财务数据 (Prev=上一天, 当前=本次):")
    print("  AssetNet 净资产:     " + str(notice["AssetNetPrev"]) + " -> " + str(asset_net))
    print("  AssetLoan 总负债:    " + str(notice["AssetLoanPrev"]) + " -> " + str(asset_loan))
    print("  RewardBusiness 业务收益: " + str(notice["RewardBusinessPrev"]) + " -> " + str(reward_business))
    print("  RewardOther 其他收益: " + str(notice["RewardOtherPrev"]) + " -> " + str(reward_other))
    print("  CostBusiness 业务成本: " + str(notice["CostBusinessPrev"]) + " -> " + str(cost_business))
    print("  CostOther 其他成本:   " + str(notice["CostOtherPrev"]) + " -> " + str(cost_other))
    print()
    # 变化率预览
    print(col(C.BOLD, "  变化率预览 (现数据/原数据 - 1):"))
    prev_map = [
        ("AssetNet", "净资产"),
        ("AssetLoan", "总负债"),
        ("RewardBusiness", "业务收益"),
        ("RewardOther", "其他收益"),
        ("CostBusiness", "业务成本"),
        ("CostOther", "其他成本"),
    ]
    for key, label in prev_map:
        prev_val = notice.get(key + "Prev", 0)
        curr_val = notice[key]
        if prev_val and prev_val != 0:
            rate = (curr_val / prev_val - 1) * 100
            rate_str = ("+" if rate > 0 else "") + str(round(rate, 2)) + "%"
            color = C.GREEN if rate > 0 else (C.RED if rate < 0 else C.RESET)
        else:
            rate_str = "N/A"
            color = C.DIM
        print("    " + label.ljust(12) + ": " + col(color, rate_str))
    
    if not confirm("确认发布此股票业绩?", no=False):
        return
    
    ng = e.data["Market"].get("NoticeGroup", {})
    if not isinstance(ng, dict):
        ng = {}
        e.data["Market"]["NoticeGroup"] = ng
    
    for key in ("NoticeNormal", "NoticeRank", "NoticeReport"):
        if key not in ng:
            ng[key] = []
    
    ng["NoticeReport"].append(notice)
    
    # 同步股票 Info 中的对应字段为新设置值
    info["AssetNet"] = asset_net
    info["AssetLoan"] = asset_loan
    info["RewardBusiness"] = reward_business
    info["RewardOther"] = reward_other
    info["CostBusiness"] = cost_business
    info["CostOther"] = cost_other
    # 同步计算字段
    net_profit = (reward_business + reward_other) - (cost_business + cost_other)
    info["NetProfit"] = net_profit
    total_assets = asset_net + asset_loan
    debt_ratio = asset_loan / total_assets if total_assets else 0
    info["DebtRatio"] = debt_ratio
    price = last_close_raw(info)            # 现价 = 最后 K 线 Close（非陈旧 PriceFact）
    volume_total = info.get("VolumeTotal", 0)
    # PE/PB 按存档×100缩放规则: 现价*VolumeTotal/(100*NetProfit)
    info["PE"] = (price * volume_total / (100 * net_profit)) if net_profit else 0
    info["PB"] = (price * volume_total / (100 * asset_net)) if asset_net else 0
    
    e.modified = True
    
    print(col(C.GREEN, "  股票业绩发布成功!"))
    print("  已添加到 NoticeGroup.NoticeReport 列表")
    print("  股票 Info 已同步更新: AssetNet / AssetLoan / RewardBusiness / RewardOther / CostBusiness / CostOther")
    print("  及计算字段 NetProfit / DebtRatio / PE / PB")
    pause()


# [extra] 社区贡献 extra 功能（公告/退市/增发/分红等），非原主干
def stock_dividend(e, pre_code=None):
    """
    股票分红子菜单: 1 现金分红, 2 送股, 3 先送股后现金分红
    
    参数:
        e (Editor): Editor 实例
        pre_code (int, optional): 预先指定的股票代码, 若提供则跳过 code 输入
    返回: None
    作者: 琛ccsy
    """
    if pre_code is None:
        code = prompt_int("股票代码", mn=1000, mx=999999)
    else:
        code = int(pre_code)
        print(col(C.CYAN, "  当前股票: X" + str(code)))
    s = e.find(code)
    if not s:
        print(col(C.RED, "  X" + str(code) + " 不存在")); pause(); return
    info = s.info._d
    price = s.info.last_close_raw          # 现价 = 最后 K 线 Close（非陈旧 PriceFact）
    flow = info.get("VolumeFlow", 0)
    total_shares = info.get("VolumeTotal", 0)
    asset_net = info.get("AssetNet", 0)
    asset_loan = info.get("AssetLoan", 0)
    total_asset = asset_net + asset_loan
    print(col(C.BOLD, "  股票 X" + str(code) + " 当前:"))
    print("    PriceFact=" + str(price) + " Flow=" + str(flow) + " Total=" + str(total_shares))
    print("    AssetNet=" + str(asset_net) + " AssetLoan=" + str(asset_loan) + " TotalAsset=" + str(total_asset))
    print()
    print("  分红类型:")
    print("    1. 现金分红         直接给所有持仓者派发现金, 股价同步下降, 总资产减少")
    print("    2. 送股(送红股)     按比例增加所有持仓股数, 股价等比例下降, 总市值不变")
    print("    3. 先送股后现金分红  先按比例送股, 再派发现金")
    print()
    print("  说明: 系统会遍历 主力/散户/玩家/NPC(5类) 的所有持仓, 自动同比例同步")
    print("        现金分红的最大 D 受 净资产 与 负债率限制, 超过会被拒绝")
    print("        送股比例: 10送X 表示每10股送X股 (例如 10送3 = 增加30%)")
    choice = prompt_int("选择分红类型 (1=现金, 2=送股, 3=先送后现)", mn=1, mx=3)
    keys = ["AloneNpc","HuddleNpc","MessageNpc","RelayNpc","SneakNpc"]
    def collect_vols():
        vols = {}
        p_entry = None
        for p in e.data["Player"].get("StockPos", []) or []:
            if p.get("Code") == code:
                p_entry = p; vols["player"] = int(p.get("VolumeUsable", 0))
        vols["inst"] = int(s.institution._d.get("VolumeUsableSell", 0))
        vols["ret"] = int(s.retail._d.get("VolumeUsableSell", 0))
        for k in keys:
            v = 0
            for acc in e.data["Market"].get(k, []) or []:
                for p in acc.get("StockPos", []) or []:
                    if p.get("Code") == code:
                        v += int(p.get("VolumeUsable", 0))
            vols[k] = v
        return vols, p_entry
    def do_cash():
        # 读取【实时】值: choice==3(先送后现)时, do_stock 已改写了价格/净资产等,
        # 这里必须重新从 info 读取, 否则现金腿会用送股前的旧数据算错。
        price = s.info.last_close_raw          # 现价 = 最后 K 线 Close
        asset_net = info.get("AssetNet", 0)
        asset_loan = info.get("AssetLoan", 0)
        total_asset = asset_net + asset_loan
        vols, _ = collect_vols()
        total_hand = sum(int(v) for v in vols.values())
        max_total_by_debt = max(0, int(total_asset * 0.70) - asset_loan)
        max_total_by_asset = max(0, int(asset_net))
        max_total = min(max_total_by_debt, max_total_by_asset)
        max_D = (max_total * 10000 // total_hand) if total_hand > 0 else 0  # 内部: max_total(内部元)*10000/total_hand(内部股)
        print("  现金分红上限计算:")
        print("    按负债率70%限: max_total_by_debt = max(0, 总资产×70% - 总负债) = " + str(max_total_by_debt))
        print("    按净资产限:    max_total_by_asset = 净资产 = " + str(max_total_by_asset))
        print("    总分红上限:    max_total = min(两者) = " + str(max_total))
        print("    总手数:        total_hand = " + str(total_hand))
        print("    最大每手分红:  max_D = max_total / 总手数 = " + str(round(max_D/100, 2)) + " 元/手")
        print()
        D = prompt_float("每手分红 D (元/100股, 需≤max_D, 0.01起)", default="1.0", mn=0.01)
        D_int = int(D * 100)
        if D_int > max_D:
            print(col(C.RED, "  D=" + str(D) + " 超过 max_D=" + str(round(max_D/100,2)) + " 元, 拒绝"))
            pause(); return False
        total_div = total_hand * D_int // 10000  # 内部元: total_hand(内部股)*D_int(分/100显示股)/10000
        print(col(C.BOLD, "  === 现金分红明细 ==="))
        print("  总分红=" + fmt_m(total_div) + "  max_D=" + str(round(max_D/100,2)) + " 元/手  实际 D=" + str(D))
        # 分发
        for k, vol in vols.items():
            add = int(vol) * D_int // 10000  # 内部元: vol(内部股)*D_int/10000
            if add == 0: continue
            if k == "player":
                e.data["Player"]["Amount"] = int(e.data["Player"].get("Amount", 0)) + add
                e.data["Player"]["AmountInit"] = int(e.data["Player"].get("AmountInit", 0)) + add
                print("  玩家 +" + fmt_m(add))
            elif k == "inst":
                s.institution._d["AmountUsableBuy"] = int(s.institution._d.get("AmountUsableBuy", 0)) + add
                print("  主力 +" + fmt_m(add))
            elif k == "ret":
                s.retail._d["AmountUsableBuy"] = int(s.retail._d.get("AmountUsableBuy", 0)) + add
                print("  散户 +" + fmt_m(add))
            else:
                for acc in e.data["Market"].get(k, []) or []:
                    for p in acc.get("StockPos", []) or []:
                        if p.get("Code") == code:
                            acc["Amount"] = int(acc.get("Amount", 0)) + int(p.get("VolumeUsable", 0)) * D_int // 10000
                print("  " + k + " +" + fmt_m(add))
        # 现金分红(除息): 只降股价 + 扣减净资产, 【不动】总股本/流通股
        # (按价格比例缩股是送股/ex-right 的语义, 不是除息)
        new_price = max(1, int(price) - int(D))  # 除息: 每股派 D/100元 => D分/股 => 现价减D
        set_price_fact_sync_candles(s.info, new_price / 100)   # 写 PriceFact + 同步最后 K 线
        info["AssetNet"] = max(0, int(asset_net) - total_div)
        info["AssetNetPrev"] = info["AssetNet"]
        info["AssetLoanPrev"] = int(asset_loan)
        print("  新 PriceFact=" + str(new_price) + " (总股本/流通股不变)")
        # 业绩公告
        ng = e.data["Market"].get("NoticeGroup", {})
        if not isinstance(ng, dict): ng = {}
        for _k in ("NoticeNormal","NoticeRank","NoticeReport"):
            ng.setdefault(_k, [])
        star = prompt_int("业绩星级 (1-5)", default=3, mn=1, mx=5)
        is_buy = prompt_int("利好(1)/利空(2)", default=1, mn=1, mx=2) == 1
        day = 1
        if info.get("Candles"):
            day = info["Candles"][-1].get("Day", 0) + 1
        rep = {"Code": code, "Buy": is_buy, "Star": star,
               "ReduceProb": 1.0/star if star else 0,
               "Prob": star * float(e.data["Market"]["NoticeStyle"].get("ReportStrength", 1.0)),
               "Day": day,
               "AssetNetPrev": asset_net, "AssetNet": info["AssetNet"],
               "AssetLoanPrev": asset_loan, "AssetLoan": asset_loan,
               "RewardBusinessPrev": info.get("RewardBusiness", 0), "RewardBusiness": info.get("RewardBusiness", 0),
               "RewardOtherPrev": info.get("RewardOther", 0), "RewardOther": info.get("RewardOther", 0),
               "CostBusinessPrev": info.get("CostBusiness", 0), "CostBusiness": info.get("CostBusiness", 0),
               "CostOtherPrev": info.get("CostOther", 0), "CostOther": info.get("CostOther", 0)}
        ng.setdefault("NoticeReport", []).append(rep)
        e.data["Market"]["NoticeGroup"] = ng
        e.modified = True
        print(col(C.GREEN, "  现金分红完成, NoticeReport 已发布"))
        pause()
        return True
    def do_stock():
        print("  送红股说明: 每10股送X股, 按比例增加所有持仓股数, 股价等比例下降, 总市值不变")
        print("  示例: 10送3 = 每10股送3股, 持仓从1000股变为1300股, 股价从10元变为约7.69元")
        X = prompt_int("10送X (填X, 例如 3 = 10送3, 10 = 10送10)", default=3, mn=1)
        r = 1 + X/10.0
        nf = int(flow * r); nt = int(total_shares * r); np2 = int(price / r)
        print(col(C.BOLD, "  === 送股明细 ==="))
        print("  10送" + str(X) + " -> Flow " + str(flow) + "->" + str(nf) + " Total " + str(total_shares) + "->" + str(nt))
        print("  PriceFact " + str(price) + "->" + str(np2))
        info["VolumeFlow"] = nf; info["VolumeTotal"] = nt
        set_price_fact_sync_candles(s.info, np2 / 100)   # 写 PriceFact + 同步最后 K 线
        if "VolumeFlowInit" in info: info["VolumeFlowInit"] = nf
        # 玩家/主力/散户/NPC 持仓同比例放大
        for p in e.data["Player"].get("StockPos", []) or []:
            if p.get("Code") == code:
                old = int(p.get("VolumeUsable", 0)); p["VolumeUsable"] = int(old * r)
                if price: p["Amount"] = int(p.get("Amount", 0) * np2 / price)
        iv = int(s.institution._d.get("VolumeUsableSell", 0))
        s.institution._d["VolumeUsableSell"] = int(iv * r)
        s.institution._d["InitVolumeSell"] = s.institution._d["VolumeUsableSell"]
        rv = int(s.retail._d.get("VolumeUsableSell", 0))
        s.retail._d["VolumeUsableSell"] = int(rv * r)
        for k in keys:
            for acc in e.data["Market"].get(k, []) or []:
                for p in acc.get("StockPos", []) or []:
                    if p.get("Code") == code:
                        ov = int(p.get("VolumeUsable", 0)); p["VolumeUsable"] = int(ov * r)
                        if price: p["Amount"] = int(p.get("Amount", 0) * np2 / price)
        e.modified = True
        print(col(C.GREEN, "  送股完成"))
        pause()
    if choice == 1: do_cash()
    elif choice == 2: do_stock()
    elif choice == 3: do_stock(); do_cash()
    print(); print(col(C.BOLD, "  分红完成"))


# [extra] 社区贡献 extra 功能（公告/退市/增发/分红等），非原主干
def stock_dividend_for_code(e, code):
    """
    针对单个股票执行分红（直接调用 stock_dividend 并传入 pre_code）
    
    参数:
        e (Editor): Editor 实例
        code (int): 股票代码
    返回: None
    作者: 琛ccsy
    """
    stock_dividend(e, pre_code=code)


# [extra] 社区贡献 extra 功能（公告/退市/增发/分红等），非原主干
def private_placement(e, pre_code=None):
    """
    定向增发: 按近20日均价80%折价, 新增流通股, 玩家认购
    
    参数:
        e (Editor): Editor 实例
        pre_code (int, optional): 预先指定的股票代码, 若提供则跳过 code 输入
    返回: None
    作者: 琛ccsy
    """
    if pre_code is None:
        code = prompt_int("股票代码", mn=1000, mx=999999)
    else:
        code = int(pre_code)
        print(col(C.CYAN, "  当前股票: X" + str(code)))
    s = e.find(code)
    if not s:
        print(col(C.RED, "  X" + str(code) + " 不存在")); pause(); return
    info = s.info
    print("  定向增发说明:")
    print("    1) 发行价 = 近20日均价 × 折价率 (例如 均价10元, 折价率0.8 => 发行价8元)")
    print("    2) 玩家按发行价支付金额, 换取对应股数, 直接加入流通股")
    print("    3) 若K线不足20日, 退化为使用 PriceFact 昨收盘价作为均价")
    print()
    candles = info._d.get("Candles", []) or []
    last20 = candles[-20:] if len(candles) >= 20 else candles
    print("  近20日均价 avg20 = 待算 (共" + str(len(last20)) + "根K线)")
    print()
    print("  折价率说明: 0.8 = 八折 (最常见), 0.7 = 七折 (便宜), 1.0 = 不折价")
    ratio = prompt_float("折价率 (0.01~1.0, 默认0.8=八折)", default="0.8", mn=0.01, mx=1.0)
    print("  玩家支付金额: 元 (内部×100存储)")
    amt_y = prompt_float("玩家支付金额 (单位:元, 建议≥10000)", default="1000000", mn=1.0)
    # 转调 core: compute_placement 算发行价/新增股数（avg20/py/pi/ns/cost）
    avg20, py, pi, ns, cost = compute_placement(candles, info.price_fact_raw, ratio, amt_y)
    print(col(C.BOLD, "  === 定向增发明细 ==="))
    print("  X" + str(code) + " avg20=" + str(round(avg20,2)) + " ratio=" + str(ratio) + " price=" + str(round(py,2)) + " 元/股")
    print("  新增 " + str(ns) + " 手  玩家支付 " + fmt_m(int(amt_y*100)))
    if not confirm("确认定向增发?", no=False):
        return
    if ns <= 0:
        print(col(C.YELLOW, "  新增为0, 跳过")); pause(); return
    # 转调 core: apply_private_placement 新增流通/总股本 + 扣玩家资金 + 登记持仓/交易记录
    apply_private_placement(e.model, code, s, ns, cost, candles)
    e.modified = True
    print(col(C.GREEN, "  定向增发完成"))
    pause()


# [extra] 社区贡献 extra 功能（公告/退市/增发/分红等），非原主干
def private_placement_for_code(e, code):
    """
    针对单个股票执行定向增发（直接调用 private_placement 并传入 pre_code）
    
    参数:
        e (Editor): Editor 实例
        code (int): 股票代码
    返回: None
    作者: 琛ccsy
    """
    private_placement(e, pre_code=code)


# [extra] 社区贡献 extra 功能（公告/退市/增发/分红等），非原主干
def issue_stock(e):
    """
    发行新股票

    支持两种来源：
    1. 退市池B集合恢复：按标准流程发行，保留原code、原财务数据（若存档有），
       无主力/散户初始持仓（VolumeUsableSell=0）。从B集合移除code。
    2. 自定义code发行：完整初始化主力(51%)/散户(49%)持仓、总市值、
       写入Name.sav、Sectors挂接。支持输入股票名称。
    
    股票代码生成逻辑：
      格式: 交易所(1位) + 板块(2位) + 序号(2位)
      例如: 1(沪) + 50(消费) + 11(序号) = 10511
      板块编码: 10金融 20科技 30工业 40能源 50消费 60医药 70交通 80房产 90环保 100农业

    参数:
        e (Editor): Editor 实例
    返回: None
    作者: 琛ccsy
    """
    pool = get_or_create_delisted_pool(e)
    b_set = pool["B"]
    codes = e.codes()

    mode = "new"
    restore_code = None

    print(col(C.BOLD, "  发行新股票"))
    print()
    print("  1. 从退市池B集合恢复")
    print("  2. 自定义code发行新股票")
    if b_set:
        print()
        print(col(C.DIM, "  B集合可选code:"))
        for i in range(0, len(b_set), 10):
            print("    " + "  ".join("X" + str(c).zfill(4) for c in b_set[i:i+10]))
    print()

    choice = prompt("来源", "2")

    if choice == "1":
        if not b_set:
            print(col(C.YELLOW, "  退市池B集合为空"))
            pause()
            return
        print("  输入要恢复的股票code:")
        restore_code = prompt_int("Code", mn=1000, mx=999999)
        if restore_code not in b_set:
            print(col(C.RED, "  X" + str(restore_code) + " 不在B集合"))
            pause()
            return
        if restore_code in codes:
            print(col(C.RED, "  X" + str(restore_code) + " 已在股票池中"))
            pause()
            return
        mode = "restore"
    elif choice == "2":
        # 新版自定义code发行: 告知生成逻辑
        print()
        print(col(C.BOLD, "  === 股票代码生成逻辑 ==="))
        print("  格式: 交易所(1位) + 板块(2位) + 序号(2位)")
        print("  交易所: 1=上交所   2=深交所")
        print("  板块: 10金融 20科技 30工业 40能源 50消费")
        print("        60医药 70交通 80房产 90环保 100农业")
        print("  示例: 1(沪) + 50(消费) + 11(序号) = 10511")
        print()
        new_code = prompt_int("自定义股票code (如 10511)", mn=1000, mx=999999)
        if new_code in codes:
            print(col(C.RED, "  X" + str(new_code) + " 已存在, 请选其他code"))
            pause()
            return
        if new_code in b_set:
            print(col(C.YELLOW, "  X" + str(new_code) + " 在退市池B集合中(冲突)"))
            pause()
            return
        mode = "new"
        restore_code = new_code
    else:
        print(col(C.RED, "  无效选项"))
        pause()
        return

    # ==================== 两种模式共用: 根据code推断交易所/板块 ====================
    new_code = restore_code
    bourse_from_code = str(new_code)[0] if len(str(new_code)) == 5 else ""
    sector_from_code = str(new_code)[1:3] if len(str(new_code)) == 5 else ""

    print()
    if mode == "restore":
        print(col(C.GREEN, "  恢复退市股票 X" + str(new_code)))
    else:
        print(col(C.GREEN, "  发行新股票 X" + str(new_code)))
    print()

    if mode == "restore":
        # === 恢复模式: 无主力/散户持仓, 使用默认财务数据 ===
        # 交易所/板块选择
        print("  Bourse 交易所选择:")
        print("    1. 上交所")
        print("    2. 深交所")
        default_bourse = int(bourse_from_code) if bourse_from_code in ("1", "2") else 1
        bourse_num = int(prompt_int("Bourse 交易所 (1=沪, 2=深)", default=default_bourse, mn=1, mx=2))

        print()
        print("  Sector 板块选择 (10个板块):")
        print("    1. 金融 (10)     2. 科技 (20)     3. 工业 (30)")
        print("    4. 能源 (40)     5. 消费 (50)     6. 医药 (60)")
        print("    7. 交通 (70)     8. 房产 (80)     9. 环保 (90)    10. 农业 (100)")
        sector_choice_map = {1: 10, 2: 20, 3: 30, 4: 40, 5: 50, 6: 60, 7: 70, 8: 80, 9: 90, 10: 100}
        default_sector_idx = 1
        for k, v in sector_choice_map.items():
            if str(v) == sector_from_code or (len(sector_from_code) == 3 and sector_from_code.zfill(3) == str(v).zfill(3)):
                default_sector_idx = k
                break
        sector_choice = prompt_int("Sector 板块 (1-10)", default=default_sector_idx, mn=1, mx=10)
        sector_num = sector_choice_map[sector_choice]

        # 从同板块模板读取 Limit/RateLimit
        sector_templates = [s for s in e.stocks() if s.info._d.get("Sector") == sector_num]
        template_stock = sector_templates[0] if sector_templates else None
        sector_limit = bool(template_stock.info._d.get("Limit", True)) if template_stock else True
        sector_rate_limit = template_stock.info._d.get("RateLimit", 0.1) if template_stock else 0.1
        if template_stock:
            print("  同板块模板: X" + str(template_stock.info._d["Code"]) + "  Limit=" + str(sector_limit) + "  RateLimit=" + str(round(sector_rate_limit*100, 1)) + "%")
        else:
            print("  同板块无模板股, 使用默认: Limit=True  RateLimit=10%")

        # 基础信息输入
        print("  === 基础信息 ===")
        print("  PriceInit 发行价: 显示价(元), 例如 10.00 = 10元 (内部会×100存储, 决定涨停/跌停基准)")
        price_init_yuan = prompt_float("PriceInit 发行价 (单位:元, 显示价)", default="10.0", mn=0.01)
        print("  VolumeTotal 总股本: 公司全部股数 (单位:股), 例如 1亿股 = 100000000")
        volume_total = prompt_int("VolumeTotal 总股本 (单位:股)", default="100000000", mn=1000000)
        print("  VolumeFlow 流通股: 可自由交易的股数 (单位:股), 通常 ≤ 总股本")
        volume_flow = prompt_int("VolumeFlow 流通股 (单位:股)", default=str(volume_total), mn=1)
        raw_price = int(price_init_yuan * 100)

        # 财务数据输入
        print()
        print("  === 财务数据 (单位:元×100, 负数合法) ===")
        print("  RewardBusiness 业务收益: 主营业务产生的收入 (元×100)")
        reward_business = prompt_int("RewardBusiness 业务收益 (元×100)", default="100000000", mn=-1000000000)
        print("  RewardOther 其他收益: 非主营收入 (元×100)")
        reward_other = prompt_int("RewardOther 其他收益 (元×100)", default="10000000", mn=-100000000)
        print("  CostBusiness 业务成本: 主营成本 (元×100, 非负)")
        cost_business = prompt_int("CostBusiness 业务成本 (元×100, 非负)", default="60000000", mn=0)
        print("  CostOther 其他成本: 其他支出 (元×100, 非负)")
        cost_other = prompt_int("CostOther 其他成本 (元×100, 非负)", default="20000000", mn=0)
        print()
        print("  === 资产负债 (单位:元×100) ===")
        print("  AssetNet 净资产: 公司实际价值 (元×100, 必须为正)")
        asset_net = prompt_int("AssetNet 净资产 (元×100, 必须为正)", default="500000000", mn=1000000)
        print("  AssetLoan 总负债: 公司负债总额 (元×100, 非负)")
        asset_loan = prompt_int("AssetLoan 总负债 (元×100, 非负)", default="300000000", mn=0)

        # 用户输入的 volume_total/volume_flow 是【显示股数】, 存档需【内部值=显示股×100】
        volume_total = volume_total * 100
        volume_flow = volume_flow * 100

        net_profit = reward_business + reward_other - cost_business - cost_other
        _info_mc = {"PriceFact": raw_price, "VolumeTotal": volume_total, "AssetNet": asset_net,
                    "RewardBusiness": reward_business, "RewardOther": reward_other,
                    "CostBusiness": cost_business, "CostOther": cost_other}
        debt_ratio = asset_loan / (asset_loan + asset_net) * 100 if (asset_loan + asset_net) else 0
        pe = calc_pe(_info_mc)
        pb = calc_pb(_info_mc)

        print()
        print("  === 即将创建的股票数据 (恢复模式) ===")
        print("  股票代码: X" + str(new_code))
        print("  PriceInit 发行价:    " + fmt_p(raw_price))
        print("  VolumeTotal 总股本:  " + str(volume_total) + " (内部值, 显示 " + str(volume_total // 100) + " 股)")
        print("  VolumeFlow 流通股:   " + str(volume_flow) + " (内部值, 显示 " + str(volume_flow // 100) + " 股)")
        print("  Bourse 交易所:       " + str(bourse_num))
        print("  Sector 板块:         " + str(sector_num))
        print()
        print("  自动计算的指标:")
        print("  NetProfit 净利润:    " + fmt_m(net_profit))
        print("  DebtRatio 负债率:    " + str(round(debt_ratio, 2)) + "%")
        print("  PE 市盈率:           " + (str(round(pe, 2)) if pe != float("inf") else "N/A"))
        print("  PB 市净率:           " + (str(round(pb, 2)) if pb != float("inf") else "N/A"))
        print()
        print("  Institution.InitVolumeSell 主力初始持仓: 0 (恢复模式无持仓)")

        if not confirm("确认恢复发行?", no=False):
            return

        new_stock = {
            "Info": {
                "Code": new_code, "Limit": sector_limit, "RateLimit": sector_rate_limit,
                "VolumeTotal": volume_total, "VolumeFlow": volume_flow, "VolumeFlowInit": volume_flow,
                "AssetNet": asset_net, "AssetNetPrev": asset_net,
                "AssetLoan": asset_loan, "AssetLoanPrev": asset_loan,
                "RewardBusiness": reward_business, "RewardBusinessPrev": reward_business,
                "RewardOther": reward_other, "RewardOtherPrev": reward_other,
                "CostBusiness": cost_business, "CostBusinessPrev": cost_business,
                "CostOther": cost_other, "CostOtherPrev": cost_other,
                "ProfitNetPrev": net_profit,
                "PriceInit": raw_price, "PriceFact": raw_price,
                "Bourse": bourse_num, "Sector": sector_num, "Candles": []
            },
            "Institution": [{"VolumeUsableSell": 0, "AmountUsableBuy": 0, "InitVolumeSell": 0, "InitAmountBuy": 0, "Pos": [], "PosSell": [], "PosBuy": []}],
            "Retail": [{"VolumeUsableSell": 0, "AmountUsableBuy": 0}]
        }

    else:
        # === 自定义发行模式: 主力51%/散户49% ===
        print()
        print("  Bourse 交易所选择:")
        print("    1. 上交所")
        print("    2. 深交所")
        bourse_num = int(prompt_int("Bourse 交易所 (1=沪, 2=深)", default=1, mn=1, mx=2))
        print()
        print("  Sector 板块选择 (10个板块):")
        print("    1. 金融 (10)     2. 科技 (20)     3. 工业 (30)")
        print("    4. 能源 (40)     5. 消费 (50)     6. 医药 (60)")
        print("    7. 交通 (70)     8. 房产 (80)     9. 环保 (90)    10. 农业 (100)")
        sector_choice_map = {1: 10, 2: 20, 3: 30, 4: 40, 5: 50, 6: 60, 7: 70, 8: 80, 9: 90, 10: 100}
        sector_choice = prompt_int("Sector 板块 (1-10)", default=1, mn=1, mx=10)
        sector_num = sector_choice_map[sector_choice]
        print()
        print("  发行价: 股票初始价格 (元/股), 例如 10.00 = 10元")
        price_yuan = prompt_float("发行价 (元)", default="10.0", mn=0.01)
        print()
        print("  流通股数: 可交易的股票数量 (手, 1手=100股)")
        floats = prompt_int("流通股数 (手)", default="10000000", mn=1)
        print()
        print("  总股本: 公司发行的全部股数 (股数), 通常 = 流通股数 × 100")
        total_shares = prompt_int("总股本 (股数)", default=str(floats * 100), mn=1)
        print()
        print("  股票名称: 显示在行情软件中的名字 (可留空)")
        name = prompt("股票名称", "")

        # 从同板块模板读取 Limit/RateLimit 和默认财务数据
        sector_templates = [s for s in e.stocks() if s.info._d.get("Sector") == sector_num]
        template_stock = sector_templates[0] if sector_templates else None
        if template_stock:
            default_info = dict(template_stock.info._d)
            print("  同板块模板: X" + str(template_stock.info._d["Code"]))
        else:
            default_info = {"Limit": True, "RateLimit": 0.10,
                            "AssetNet": 500000000, "AssetLoan": 300000000,
                            "RewardBusiness": 100000000, "RewardOther": 10000000,
                            "CostBusiness": 60000000, "CostOther": 20000000}

        raw_price = int(price_yuan * 100)
        inst_vol = int(floats * 0.51)          # 手
        retail_vol = floats - inst_vol          # 手
        # 存档约定: VolumeFlow/VolumeUsable* 存【内部值 = 显示股×100】;
        # 用户输入 floats(手,1手=100显示股) 与 total_shares(显示股) 需先转成内部值。
        inst_vol_internal = inst_vol * 10000    # 手 -> 显示股(×100) -> 内部(×100)
        retail_vol_internal = retail_vol * 10000
        floats_internal = floats * 10000        # VolumeFlow 内部值
        total_shares_internal = total_shares * 100  # VolumeTotal 内部值
        # 总市值(显示元) = 显示价×显示股 = (raw_price/100)×total_shares
        market_cap_yuan = int(raw_price * total_shares / 100)
        inst_buy = int(market_cap_yuan * 0.51 * 100)   # 内部金额(分): 元×100
        retail_buy = int(market_cap_yuan * 0.49 * 100)

        print()
        print(col(C.BOLD, "  === 发行明细 ==="))
        print("  Code=" + str(new_code) + " Sector=" + str(sector_num) + " Bourse=" + str(bourse_num))
        print("  发行价=" + fmt_p(raw_price) + " 流通=" + str(floats) + " 手 总股本=" + str(total_shares))
        print("  主力: " + str(inst_vol) + " 手 (51%)  AmountUsableBuy=" + fmt_p(inst_buy))
        print("  散户: " + str(retail_vol) + " 手  AmountUsableBuy=" + fmt_p(retail_buy))
        print("  总市值=" + fmt_m(market_cap_yuan))
        if not confirm("确认发行?", no=False):
            return

        # 写入 Name.sav
        if name:
            try:
                save_dir = e.path.parent
                nf = save_dir / "Name.sav"
                nd = {"StockName": {}, "RoleName": []}
                if nf.exists():
                    with open(nf, "r", encoding="utf-8") as _f:
                        nd = json.load(_f) or {"StockName": {}, "RoleName": []}
                nd.setdefault("StockName", {})
                nd["StockName"][str(new_code)] = name
                with open(nf, "w", encoding="utf-8") as _f:
                    json.dump(nd, _f, ensure_ascii=False, indent=2)
                print(col(C.DIM, "  已写入 Name.sav: X" + str(new_code) + " => " + str(name)))
            except Exception as _ex:
                print(col(C.YELLOW, "  写 Name.sav 失败: " + str(_ex)))

        new_stock = {
            "Info": {
                "Code": new_code,
                "Limit": default_info.get("Limit", True),
                "RateLimit": default_info.get("RateLimit", 0.10),
                "VolumeTotal": total_shares_internal, "VolumeFlow": floats_internal, "VolumeFlowInit": floats_internal,
                "AssetNet": default_info.get("AssetNet", 0),
                "AssetNetPrev": default_info.get("AssetNet", 0),
                "AssetLoan": default_info.get("AssetLoan", 0),
                "AssetLoanPrev": default_info.get("AssetLoan", 0),
                "RewardBusiness": default_info.get("RewardBusiness", 0),
                "RewardBusinessPrev": default_info.get("RewardBusiness", 0),
                "RewardOther": default_info.get("RewardOther", 0),
                "RewardOtherPrev": default_info.get("RewardOther", 0),
                "CostBusiness": default_info.get("CostBusiness", 0),
                "CostBusinessPrev": default_info.get("CostBusiness", 0),
                "CostOther": default_info.get("CostOther", 0),
                "CostOtherPrev": default_info.get("CostOther", 0),
                "ProfitNetPrev": (default_info.get("RewardBusiness", 0) + default_info.get("RewardOther", 0)
                                  - default_info.get("CostBusiness", 0) - default_info.get("CostOther", 0)),
                "PriceInit": raw_price, "PriceFact": raw_price,
                "Bourse": bourse_num, "Sector": sector_num, "Candles": []
            },
            "Institution": [{
                "VolumeUsableSell": inst_vol_internal, "AmountUsableBuy": inst_buy,
                "InitVolumeSell": inst_vol_internal, "InitAmountBuy": inst_buy,
                "Pos": [], "PosSell": [], "PosBuy": []
            }],
            "Retail": [{"VolumeUsableSell": retail_vol_internal, "AmountUsableBuy": retail_buy}]
        }

    # ==================== 两种模式共用: 加入股票池 & Sectors 挂接 ====================
    # 生成初始 Candles 对象 (Day=1, 价格统一为发行价)
    # VolumeFlow 现已是内部值(显示股×100), Candle.Volume 保持原量级(=流通手数/100)
    init_volume = max(1, int(new_stock["Info"].get("VolumeFlow", 0) / 10000))
    init_candle = {
        "Day": 1,
        "Open": raw_price,
        "Close": raw_price,
        "High": raw_price,
        "Low": raw_price,
        "Volume": init_volume,
        "Amount": init_volume * raw_price
    }
    new_stock["Info"]["Candles"] = [init_candle]
    print(col(C.DIM, "  已生成初始K线 Candles: Day=1 Close=" + str(raw_price) + " Volume=" + str(init_volume)))
    e.data["Market"]["Stocks"].append(new_stock)

    sectors = e.data["Market"].get("Sectors", [])
    if not isinstance(sectors, list):
        sectors = []
        e.data["Market"]["Sectors"] = sectors

    for sector_code in (sector_num, int(bourse_num)):
        found = None
        for s_obj in sectors:
            if isinstance(s_obj, dict) and s_obj.get("Code") == sector_code:
                found = s_obj
                break
        if found is None:
            found = {"Code": sector_code, "StockCodes": []}
            sectors.append(found)
        stock_codes = found.get("StockCodes")
        if not isinstance(stock_codes, list):
            stock_codes = []
            found["StockCodes"] = stock_codes
        if new_code not in stock_codes:
            stock_codes.append(new_code)

    # 若从B集合恢复，从B中移除code
    if mode == "restore" and restore_code in b_set:
        b_set.remove(restore_code)
        print(col(C.DIM, "  已从退市池B集合移除 X" + str(restore_code)))

    e.modified = True
    print()
    print(col(C.GREEN, "  股票 X" + str(new_code) + " 发行成功!"))
    pause()
    return new_stock


# [extra] 社区贡献 extra 功能（公告/退市/增发/分红等），非原主干
def _view_notice_list(e, ng, notices, code, notice_type):
    """
    查看指定类型的公告列表
    
    参数:
        e: Editor 编辑器实例
        ng: NoticeGroup 字典
        notices: 公告列表
        code: 股票代码
        notice_type: "normal" (股票公告) 或 "report" (业绩报告)
    
    返回:
        无
    """
    while True:
        clear()
        type_name = "股票公告" if notice_type == "normal" else "业绩报告"
        list_key = "NoticeNormal" if notice_type == "normal" else "NoticeReport"
        print(col(C.BOLD, "  股票 X" + str(code) + " " + type_name + "列表 (" + str(len(notices)) + " 条)"))
        hr()
        
        for i, n in enumerate(notices):
            idx = i + 1
            buy_text = col(C.RED, "利好") if n.get("Buy", False) else col(C.GREEN, "利空")
            star = n.get("Star", 0)
            star_display = col(C.YELLOW, "★" * star + "☆" * (5 - star))
            prob = n.get("Prob", 0)
            day = n.get("Day", 0)
            print("  " + str(idx) + ". " + buy_text + " " + star_display + "  影响: " + str(round(prob, 4)) + "  发布时间: Day " + str(day))
        
        hr()
        print("  输入序号查看详情 (0=返回)")
        print("  输入 d+序号 删除 (例如 d1)")
        print()
        
        ch = prompt("选择", "0")
        
        if ch == "0" or ch.lower() == "x":
            return
        
        if ch.lower().startswith("d"):
            try:
                idx = int(ch[1:])
                if 1 <= idx <= len(notices):
                    if confirm("删除第 " + str(idx) + " 条" + type_name + "?", no=True):
                        notice_to_delete = notices[idx - 1]
                        ng[list_key].remove(notice_to_delete)
                        notices.pop(idx - 1)
                        e.modified = True
                        print(col(C.GREEN, "  已删除"))
                        pause()
                else:
                    print(col(C.RED, "  序号超出范围"))
                    pause()
            except (ValueError, IndexError):
                print(col(C.RED, "  格式错误"))
                pause()
            continue
        
        try:
            idx = int(ch)
            if 1 <= idx <= len(notices):
                if notice_type == "normal":
                    show_notice_detail(notices[idx - 1])
                else:
                    # 查找对应股票传递给 show_report_detail
                    target_stock = e.find(notices[idx - 1].get("Code"))
                    show_report_detail(notices[idx - 1], stock=target_stock)
                pause()
            else:
                print(col(C.RED, "  序号超出范围"))
                pause()
        except ValueError:
            print(col(C.RED, "  无效输入"))
            pause()


# [extra] 社区贡献 extra 功能（公告/退市/增发/分红等），非原主干
def publish_notice(e, default_code=None):
    """
    发布公告
    
    支持三种类型:
    1. 市场公告: 固定 Code=0, 创建 NoticeNormal
    2. 板块公告: 用户选择板块 Code, 创建 NoticeNormal
    3. 股票公告: 创建 NoticeNormal, 支持批量（逗号分隔）
    4. 股票业绩: 创建 NoticeReport
    
    Prob 公式 (新):
      NoticeNormal (股票/板块/市场):
        Prob = Star × Normal*Strength
        ReduceProb = Normal*CreateProb / Star
      NoticeReport (股票业绩):
        Prob = Star × ReportStrength
        ReduceProb = 1 / Star
    
    参数:
        e: Editor 编辑器实例
        default_code: 默认股票代码 (单支股票菜单调用时传入, 可选)
        default_mode: 默认类型 (可选)
    
    返回:
        无
    """
    codes = e.codes()
    
    # 显示菜单
    if default_code is None:
        # 主菜单调用: 显示全部股票
        print(col(C.BOLD, "  发布公告"))
        print("  当前股票列表:")
        for i in range(0, len(codes), 10):
            print("  " + "  ".join("X" + str(c).zfill(4) for c in codes[i:i+10]))
        print()
        print("  1. 市场公告   - 固定 Code=0 (NoticeNormal, 利好/利空)")
        print("  2. 板块公告   - 选择板块代码 (NoticeNormal, 利好/利空)")
        print("  3. 股票公告   - 选择股票代码 (NoticeNormal, 支持批量)")
        print("  4. 股票业绩   - 创建 NoticeReport (财务数据同步)")
        print()
        mode = prompt_int("类型 (1=市场, 2=板块, 3=股票公告, 4=股票业绩)", default=1, mn=1, mx=4)
    else:
        # 单支股票菜单调用: 锁定当前股票代码
        stock = e.find(default_code)
        if not stock:
            print(col(C.RED, "  股票 X" + str(default_code) + " 不存在"))
            pause()
            return
        info = stock.info._d
        sector_num = info.get("Sector", 0)
        bourse_num = info.get("Bourse", 0)
        print(col(C.BOLD, "  发布公告 (股票 X" + str(default_code) + ")"))
        print("  Sector 板块: " + SECTOR_MAP.get(sector_num, str(sector_num)) + "板块  Bourse 交易所: " + BOURSE_MAP.get(bourse_num, str(bourse_num)))
        print()
        print("  1. 股票公告   - 针对当前股票 X" + str(default_code) + " (NoticeNormal)")
        print("  2. 股票业绩   - 针对当前股票 X" + str(default_code) + " (NoticeReport)")
        print()
        mode = prompt_int("类型 (1=股票公告, 2=股票业绩)", default=1, mn=1, mx=2)
        mode = mode + 2
    
    # ========= 1. 市场公告 =========
    if mode == 1:
        stock_for_day = e.find(codes[0]) if codes else None
        current_day = get_current_game_day(stock_for_day) if stock_for_day else 0
        notice_day = current_day + 1
        ns = e.data["Market"].get("NoticeStyle", {})
        mkt_strength = float(ns.get("NormalMarketStrength", 1.0))
        mkt_create_prob = float(ns.get("NormalMarketCreateProb", 0.08))
        print("  当前游戏天数: " + str(current_day))
        print("  公告发布时间: Day " + str(notice_day) + " (当前+1)")
        print("  目标 Code: 0 (市场)")
        print("  NormalMarketStrength: " + str(round(mkt_strength, 4)))
        print("  NormalMarketCreateProb: " + str(round(mkt_create_prob, 4)))
        
        star = prompt_int("Star 星级 (0-5)", default=3, mn=0, mx=5)
        is_buy = prompt_int("Type 类型 (1=利好, 2=利空)", default=1, mn=1, mx=2) == 1
        market_notice = _build_stock_notice(0, {"Info": {"RateLimit": 0.10}}, notice_day, star, strength=mkt_strength, create_prob=mkt_create_prob)
        market_notice["Buy"] = is_buy
        
        print()
        print(col(C.BOLD + C.CYAN, "  === 即将发布的市场公告 (NoticeNormal) ==="))
        _print_notice_preview(market_notice, "市场公告")
        
        if not confirm("确认发布市场公告?", no=False):
            return
        
        _append_notice_normal(e, [market_notice])
        return
    
    # ========= 2. 板块公告 =========
    if mode == 2:
        print("  可选板块:")
        for code, name in SECTOR_MAP.items():
            print("    " + str(code) + " - " + name)
        print()
        sector_code = prompt_int("选择板块代码 (如 90=环保)", default=10, mn=10, mx=100)
        if sector_code not in SECTOR_MAP:
            print(col(C.RED, "  无效板块代码"))
            pause()
            return
        current_day = 0
        if codes:
            s = e.find(codes[0])
            current_day = get_current_game_day(s)
        notice_day = current_day + 1
        ns = e.data["Market"].get("NoticeStyle", {})
        sector_strength = float(ns.get("NormalSectorStrength", 1.0))
        sector_create_prob = float(ns.get("NormalSectorCreateProb", 0.08))
        print("  当前游戏天数: " + str(current_day))
        print("  公告发布时间: Day " + str(notice_day) + " (当前+1)")
        print("  目标板块 Code: " + str(sector_code) + " (" + SECTOR_MAP[sector_code] + ")")
        print("  NormalSectorStrength: " + str(round(sector_strength, 4)))
        print("  NormalSectorCreateProb: " + str(round(sector_create_prob, 4)))
        
        star = prompt_int("Star 星级 (0-5)", default=3, mn=0, mx=5)
        is_buy = prompt_int("Type 类型 (1=利好, 2=利空)", default=1, mn=1, mx=2) == 1
        sector_notice = _build_stock_notice(sector_code, {"Info": {"RateLimit": 0.10}}, notice_day, star, strength=sector_strength, create_prob=sector_create_prob)
        sector_notice["Buy"] = is_buy
        
        print()
        print(col(C.BOLD + C.CYAN, "  === 即将发布的板块公告 (NoticeNormal) ==="))
        _print_notice_preview(sector_notice, "板块公告[" + SECTOR_MAP[sector_code] + "]")
        
        if not confirm("确认发布板块公告?", no=False):
            return
        
        _append_notice_normal(e, [sector_notice])
        return
    
    # ========= 3. 股票公告 (NoticeNormal, 支持批量) =========
    if mode == 3:
        if default_code is not None:
            valid_codes = [default_code]
        else:
            codes_input = prompt("输入股票代码 (多个用逗号/空格分隔, 例如 2075,3011)", "2075")
            code_list = []
            for c in codes_input.split(","):
                c = c.strip()
                if c.isdigit():
                    code_list.append(int(c))
            
            if not code_list:
                print(col(C.RED, "  没有有效的股票代码"))
                pause()
                return
            
            valid_codes = []
            invalid_codes = []
            for code in code_list:
                if code in codes:
                    valid_codes.append(code)
                else:
                    invalid_codes.append(code)
            
            if invalid_codes:
                print(col(C.YELLOW, "  以下代码不存在: " + ", ".join(str(c) for c in invalid_codes)))
                if not valid_codes:
                    pause()
                    return
        
        stock = e.find(valid_codes[0])
        current_day = get_current_game_day(stock)
        notice_day = current_day + 1
        ns = e.data["Market"].get("NoticeStyle", {})
        stock_strength = float(ns.get("NormalStockStrength", 1.0))
        stock_create_prob = float(ns.get("NormalStockCreateProb", 0.02))
        print("  当前游戏天数: " + str(current_day))
        print("  公告发布时间: Day " + str(notice_day) + " (当前+1)")
        print("  待发布股票数: " + str(len(valid_codes)))
        print("  NormalStockStrength: " + str(round(stock_strength, 4)))
        print("  NormalStockCreateProb: " + str(round(stock_create_prob, 4)))
        
        star = prompt_int("Star 星级 (0-5)", default=3, mn=0, mx=5)
        is_buy = prompt_int("Type 类型 (1=利好, 2=利空)", default=1, mn=1, mx=2) == 1
        
        # 预构建所有 NoticeNormal 对象
        print()
        print(col(C.BOLD + C.CYAN, "  === 预构建 NoticeNormal 列表 (共 " + str(len(valid_codes)) + " 条) ==="))
        preview_list = []
        for code in valid_codes:
            stock_item = e.find(code)
            if stock_item:
                n = _build_stock_notice(code, stock_item, notice_day, star, strength=stock_strength, create_prob=stock_create_prob)
                n["Buy"] = is_buy
                preview_list.append(n)
            else:
                print(col(C.RED, "  ✗ X" + str(code) + " 不存在，已跳过"))
        
        if not preview_list:
            print(col(C.RED, "  没有可发布的公告"))
            pause()
            return
        
        print()
        print(col(C.BOLD + C.CYAN, "  === 即将发布的 NoticeNormal 数据 ==="))
        for i, n in enumerate(preview_list):
            print("  [" + str(i+1) + "]")
            _print_notice_preview(n, "股票 X" + str(n["Code"]))
            print()
        
        if not confirm("确认发布以上 " + str(len(preview_list)) + " 条股票公告?", no=False):
            return
        
        _append_notice_normal(e, preview_list)
        return
    
    # ========= 4. 股票业绩 (NoticeReport) =========
    if mode == 4:
        if default_code is not None:
            code = default_code
        else:
            code = prompt_int("输入股票代码", mn=1000, mx=999999)
        
        if code not in codes:
            print(col(C.RED, "  股票 X" + str(code) + " 不存在"))
            pause()
            return
        
        stock = e.find(code)
        info = stock.info._d
        current_day = get_current_game_day(stock)
        notice_day = current_day + 1
        print("  当前游戏天数: " + str(current_day))
        print("  公告发布时间: Day " + str(notice_day) + " (当前+1)")
        
        # 根据 default_code 是否存在决定输入模式
        # default_code != None 表示从个股菜单进入，保持旧的绝对值输入
        # default_code == None 表示从主菜单进入，使用变化率输入
        use_change_rate = (default_code is None)
        _create_stock_performance(e, code, stock, notice_day, use_change_rate=use_change_rate)


# [extra] 社区贡献 extra 功能（公告/退市/增发/分红等），非原主干
def view_notices(e, code):
    """
    查看指定股票的公告列表
    
    支持两种类型:
    1. 股票公告 (NoticeNormal)
    2. 业绩报告 (NoticeReport)
    
    进入后先选择类型，再查看列表和详情。
    
    参数:
        e: Editor 编辑器实例
        code: 股票代码
    
    返回:
        无
    """
    ng = e.data["Market"].get("NoticeGroup", {})
    if not isinstance(ng, dict):
        ng = {}
    
    stock_notices = [n for n in ng.get("NoticeNormal", []) if n.get("Code") == code]
    stock_reports = [r for r in ng.get("NoticeReport", []) if r.get("Code") == code]
    # 按 Day 倒序显示
    stock_notices.sort(key=lambda x: x.get("Day", 0), reverse=True)
    stock_reports.sort(key=lambda x: x.get("Day", 0), reverse=True)
    
    while True:
        clear()
        print(col(C.BOLD, "  股票 X" + str(code) + " 公告列表"))
        hr()
        print("  1. 股票公告 (" + str(len(stock_notices)) + " 条) - NoticeNormal")
        print("  2. 业绩报告 (" + str(len(stock_reports)) + " 条) - NoticeReport")
        print()
        print("  x. 返回股票菜单")
        print()
        
        ch = prompt("选择类型", "1")
        
        if ch.lower() == "x":
            return
        
        if ch == "1":
            if not stock_notices:
                print(col(C.YELLOW, "  股票 X" + str(code) + " 暂无股票公告"))
                pause()
                continue
            _view_notice_list(e, ng, stock_notices, code, "normal")
        elif ch == "2":
            if not stock_reports:
                print(col(C.YELLOW, "  股票 X" + str(code) + " 暂无业绩报告"))
                pause()
                continue
            _view_notice_list(e, ng, stock_reports, code, "report")


# [extra] 社区贡献 extra 功能（公告/退市/增发/分红等），非原主干
def delist_stock(e):
    """
    股票退市操作
    
    === 退市筛选逻辑 ===
    A集合 (警告退市):
      - 负债率 > 80%
      - 最近5条业绩报告(NoticeReport)净利润均为负
      - 进入A集合后 RateLimit 限制为 5%
      - 仍保留在股票池，可交易
    
    B集合 (完全退市):
      - 从A集合再次退市
      - 从股票池删除
      - 清除所有相关公告
      - 删除玩家持仓，差值即真实亏损
      - 不可恢复
    
    此外支持: 用户直接输入任意code进行强制退市
    """
    pool = get_or_create_delisted_pool(e)
    a_set = pool["A"]
    b_set = pool["B"]
    
    # 显示筛选逻辑说明
    print(col(C.BOLD, "  股票退市"))
    print()
    print(col(C.BOLD + C.CYAN, "  === 退市筛选逻辑 ==="))
    print("  A集合 (警告退市):")
    print("    - 负债率 > 80%")
    print("    - 最近5条业绩报告净利润均为负")
    print("    - 进入后 RateLimit 限制为 5%，仍保留在股票池")
    print()
    print("  B集合 (完全退市):")
    print("    - 从A集合再次退市")
    print("    - 从股票池删除，清除所有相关公告")
    print("    - 删除玩家持仓，差值即真实亏损")
    print("    - 不可恢复")
    print()
    print(col(C.BOLD + C.CYAN, "  === 退市池状态 ==="))
    print("  A集合(警告): " + str(len(a_set)) + " 只")
    print("  B集合(退市): " + str(len(b_set)) + " 只")
    if a_set:
        print("  A集合代码: " + " ".join("X" + str(c).zfill(4) for c in a_set))
    if b_set:
        print("  B集合代码: " + " ".join("X" + str(c).zfill(4) for c in b_set))
    print()
    
    # 步骤1: 处理 A 集合 -> B 集合
    if a_set:
        print(col(C.BOLD + C.RED, "  === 步骤1: A集合二次退市 (-> B集合) ==="))
        print(col(C.DIM, "  以下为A集合股票(警告退市), 二次退市将完全删除 (进入B集合, 不可恢复)"))
        for i in range(0, len(a_set), 10):
            print("  " + "  ".join(col(C.RED, "X" + str(c).zfill(4)) for c in a_set[i:i+10]))
        print()
        print("  输入要二次退市的股票代码 (支持逗号/空格分隔, 例如 1001,1002)")
        print("  直接回车跳过此步骤")
        codes_input = prompt("  二次退市代码", "")
        if codes_input.strip():
            code_list = []
            for c in codes_input.split(","):
                c = c.strip()
                if c.isdigit():
                    code_list.append(int(c))
            success_count = 0
            for code in code_list:
                if code not in a_set:
                    print(col(C.YELLOW, "  跳过 X" + str(code) + "  (不在A集合)"))
                    continue
                stock = e.find(code)
                if stock:
                    # 从股票池删除
                    e.data["Market"]["Stocks"] = [s for s in e.data["Market"]["Stocks"] if s["Info"]["Code"] != code]
                # 从公告记录删除
                ng = e.data["Market"].get("NoticeGroup", {})
                if isinstance(ng, dict):
                    for key in list(ng.keys()):
                        ng[key] = [item for item in ng[key] if item.get("Code") != code]
                elif isinstance(ng, list):
                    e.data["Market"]["NoticeGroup"] = [item for item in ng if item.get("Code") != code]
                # 删除玩家持仓(差值即真实亏损)
                sp = e.data["Player"].get("StockPos", [])
                removed = [p for p in sp if p.get("Code") == code]
                for rm in removed:
                    pos_amount = rm.get("Amount", 0)
                    vol = rm.get("VolumeUsable", 0)
                    price = 0
                    if stock:
                        price = stock.info._d.get("PriceFact", 0)
                    loss = pos_amount + vol * price
                    print("  X" + str(code) + " 持仓已清仓  盈亏=" + str(pos_amount) + "  股数=" + str(vol) + "  估算=" + str(loss))
                e.data["Player"]["StockPos"] = [p for p in sp if p.get("Code") != code]
                # 从A移除，加入B
                a_set.remove(code)
                if code not in b_set:
                    b_set.append(code)
                success_count += 1
                print(col(C.RED, "  ✓ X" + str(code) + " 已二次退市，进入B集合"))
            e.modified = True
            if success_count:
                print(col(C.GREEN, "  二次退市完成: " + str(success_count) + " 只"))
                pause()
        print()
    
    # 步骤2: 筛选候选 A 集合
    candidates = _filter_delisted_candidates(e)
    candidate_codes = [c for c, _, _ in candidates if c not in a_set and c not in b_set]
    
    if candidate_codes:
        print(col(C.BOLD + C.YELLOW, "  === 步骤2: 候选 A 集合 (高负债>80% + 连续5次业绩亏损) ==="))
        for code, dr, cnt in candidates:
            if code in a_set or code in b_set:
                continue
            print("  " + col(C.YELLOW, "X" + str(code).zfill(4)) + "  负债率 " + str(round(dr, 2)) + "%  最近5条业绩全为负")
        print()
        print("  输入要退市的股票代码 (支持逗号/空格分隔, 例如 1001,1002)")
        print("  直接回车跳过")
        codes_input = prompt("  候选退市代码", "")
        if codes_input.strip():
            code_list = []
            for c in codes_input.split(","):
                c = c.strip()
                if c.isdigit():
                    code_list.append(int(c))
            success_count = 0
            for code in code_list:
                if code not in candidate_codes:
                    print(col(C.YELLOW, "  跳过 X" + str(code) + "  (不满足筛选条件)"))
                    continue
                stock = e.find(code)
                if not stock:
                    print(col(C.RED, "  X" + str(code) + " 不存在"))
                    continue
                info = stock.info._d
                info["RateLimit"] = 0.05
                if code not in a_set:
                    a_set.append(code)
                success_count += 1
                print(col(C.YELLOW, "  ✓ X" + str(code) + " 已进入A集合  RateLimit=5%"))
            e.modified = True
            if success_count:
                print(col(C.GREEN, "  候选退市完成: " + str(success_count) + " 只"))
                pause()
    else:
        print()
        print(col(C.DIM, "  步骤2: 无符合筛选条件的候选股票"))
    
    print()
    
    # 步骤3: 强制退市（任意code）
    force_choice = prompt("  步骤3: 是否强制退市任意code? (y/N)", "N")
    if force_choice.lower() == "y":
        print()
        print(col(C.BOLD + C.CYAN, "  === 强制退市 ==="))
        print(col(C.YELLOW, "  强制退市不受筛选条件限制"))
        print(col(C.YELLOW, "  - 直接进入B集合 (完全退市)"))
        print(col(C.YELLOW, "  - 从股票池删除、清除公告、删除玩家持仓"))
        print()
        print("  输入要强制退市的股票代码 (支持逗号/空格分隔, 例如 1001,1002)")
        print("  直接回车取消")
        codes_input = prompt("  强制退市代码", "")
        if codes_input.strip():
            code_list = []
            for c in codes_input.split(","):
                c = c.strip()
                if c.isdigit():
                    code_list.append(int(c))
            success_count = 0
            for code in code_list:
                if code in b_set:
                    print(col(C.YELLOW, "  跳过 X" + str(code) + "  (已在B集合)"))
                    continue
                stock = e.find(code)
                if stock:
                    # 从股票池删除
                    e.data["Market"]["Stocks"] = [s for s in e.data["Market"]["Stocks"] if s["Info"]["Code"] != code]
                    print("  X" + str(code) + " 已从股票池删除")
                elif code not in a_set:
                    # 股票池不存在且不在A集合，无法强制
                    print(col(C.RED, "  跳过 X" + str(code) + "  (股票池和A集合均不存在)"))
                    continue
                # 从公告记录删除
                ng = e.data["Market"].get("NoticeGroup", {})
                if isinstance(ng, dict):
                    for key in list(ng.keys()):
                        ng[key] = [item for item in ng[key] if item.get("Code") != code]
                elif isinstance(ng, list):
                    e.data["Market"]["NoticeGroup"] = [item for item in ng if item.get("Code") != code]
                # 删除玩家持仓
                sp = e.data["Player"].get("StockPos", [])
                removed = [p for p in sp if p.get("Code") == code]
                for rm in removed:
                    pos_amount = rm.get("Amount", 0)
                    vol = rm.get("VolumeUsable", 0)
                    price = 0
                    if stock:
                        price = stock.info._d.get("PriceFact", 0)
                    loss = pos_amount + vol * price
                    print("    清仓持仓: 盈亏=" + str(pos_amount) + "  股数=" + str(vol) + "  估算亏损=" + str(loss))
                e.data["Player"]["StockPos"] = [p for p in sp if p.get("Code") != code]
                # 从A移除，加入B
                if code in a_set:
                    a_set.remove(code)
                if code not in b_set:
                    b_set.append(code)
                success_count += 1
                print(col(C.RED, "  ✓ X" + str(code) + " 已强制退市，进入B集合"))
            e.modified = True
            if success_count:
                print(col(C.GREEN, "  强制退市完成: " + str(success_count) + " 只"))
                pause()
    
    print()
    print(col(C.BOLD, "  当前退市池最终状态:"))
    print("  A集合(警告): " + str(len(a_set)) + " 只")
    print("  B集合(退市): " + str(len(b_set)) + " 只")
    pause()


# ====== 主菜单（全局操作） ======
def main_menu(e):
    """主菜单 - 全局操作"""
    while True:
        clear()
        print(col(C.BOLD + C.GREEN, "="*70))
        print(col(C.BOLD + C.GREEN, "  StocksMainForceSimulator Save Editor (终极防覆盖版)"))
        print(col(C.BOLD + C.GREEN, "="*70))
        print("  File: " + str(e.path))
        print("  Stocks: " + str(len(e.stocks())))
        if e.modified: print(col(C.YELLOW, "  * UNSAVED *"))
        print()
        print("  --- Global 全局 ---")
        print("  1.  Operate single stock    -- 操作单个股票 (进入子菜单)")
        print("  2.  Show all stocks list    -- 查看所有股票列表")
        print("  3.  Change NoticeStyle      -- 改购买取向 (NPC买入/卖出力度, 全局)")
        print("  4.  Change Player.StockPos  -- 改你的持仓 (带筹码守恒与智能增发)")
        print("  --- Market 市场操作 ---")
        print("  5.  Issue new stock         -- 发行新股票 (退市池恢复 或 自定义代码)")
        print("  6.  Delist stock            -- 股票退市 (A集合警告/B集合完全退市)")
        print("  7.  Publish notice          -- 发布公告 (市场/板块/股票公告 或 业绩报告)")
        print("  8.  Stock dividend          -- 股票分红 (现金分红/送股/先送后现)")
        print("  9.  Private placement       -- 定向增发 (按近20日均价×折价率)")
        print("  --- Cleanup 清理 ---")
        print("  10. Market rectification    -- 市场整顿 (强制 sum_hold == VolumeFlow)")
        print("  11. NPC positions -> Retail -- 全市场砍机构持仓 转散户")
        print("  12. Clear NoticeGroup       -- 清空公告历史 (减小文件)")
        print("  13. Trim HuddleNpc positions -- 砍机构持仓 (提升性能)")
        print("  14. Clear Player.TradeType  -- 清空交易历史")
        print("  --- File 文件 ---")
        print("  15. Save                    -- 保存 (带进程防覆盖检测)")
        print("  16. Reload                  -- 重新加载")
        print("  17. Exit                    -- 退出")
        print()
        ch = prompt("Choose", "1")
        if not ch.isdigit(): continue
        ch = int(ch)
        
        if ch == 1:
            codes = e.codes()
            if not codes:
                print(col(C.RED, "  No stocks found!"))
                pause()
                continue
            print(col(C.BOLD, "  Available stock codes:"))
            for i in range(0, len(codes), 10):
                print("  " + "  ".join("X" + str(c).zfill(4) for c in codes[i:i+10]))
            print()
            code = prompt_int("Enter stock code (e.g. 2075 or X2075)", mn=1000, mx=9999, extract_code=True)
            if e.find(code):
                stock_menu(e, code)
            else:
                print(col(C.RED, "  Stock X" + str(code) + " not found!"))
                pause()
        elif ch == 2:
            show_all_stocks(e)
            pause()
        elif ch == 3: change_ns(e)
        elif ch == 4: change_player(e)
        elif ch == 5: issue_stock(e)
        elif ch == 6: delist_stock(e)
        elif ch == 7: publish_notice(e)
        elif ch == 8: stock_dividend(e)
        elif ch == 9: private_placement(e)
        elif ch == 10: market_rectification(e)
        elif ch == 11: change_npc_all_to_retail(e)
        elif ch == 12: clean_ng(e)
        elif ch == 13: trim_hn(e)
        elif ch == 14: clean_tt(e)
        elif ch == 15:
            if e.save(): print(col(C.GREEN, "  Saved! (存档已安全写入)"))
            else: print(col(C.YELLOW, "  No changes to save (或取消保存)"))
            pause()
        elif ch == 16:
            e.load()
            print(col(C.GREEN, "  Reloaded!"))
            pause()
        elif ch == 17:
            if e.modified and not confirm("Unsaved changes, exit?", no=True):
                continue
            return

def parse_args(argv=None):
    import argparse
    p = argparse.ArgumentParser(
        prog="python -m src.tui.frontend.app",
        description="StocksMainForceSimulator 存档编辑器 (终极防覆盖版)",
    )
    p.add_argument("-d", "--save-dir", dest="save_dir", default=str(DEFAULT_SAVE_DIR),
                   help="存档目录路径 (默认: %(default)s)")
    args = p.parse_args(argv)
    args.save_dir = Path(args.save_dir)
    return args

def main():
    args = parse_args()
    enable_ansi()
    clear()
    print(col(C.BOLD + C.CYAN, "StocksMainForceSimulator Save Editor (终极防覆盖版)"))
    print()
    print(col(C.DIM, "  存档目录: " + str(args.save_dir)))
    print()

    # 启动时友情提示
    if is_game_running():
        print(col(C.RED, "  ⚠️ 警告：检测到游戏正在运行！"))
        print(col(C.YELLOW, "  建议先彻底关闭游戏再修改，否则保存时可能会被游戏自动保存覆盖。"))
        pause()

    d = select_save_dir(args.save_dir)
    if not d: pause(); return
    p = select_save_file(d)
    if not p: pause(); return
    e = Editor(p)
    try: e.load()
    except Exception as ex:
        print(col(C.RED, "Load failed: " + str(ex))); pause(); return
    print(col(C.GREEN, "  Loaded " + e.path.name + " (" + str(len(e.stocks())) + " stocks)"))
    pause()
    main_menu(e)

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print(col(C.YELLOW, "Interrupted."))
    except Exception as ex:
        import traceback
        print(col(C.RED, "Error: " + str(ex)))
        traceback.print_exc()
        pause()