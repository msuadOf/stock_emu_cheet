# StocksMainForceSimulator 存档编辑器 - 通用 TUI 工具
# 支持任意存档、任意股票的所有改档操作
# 菜单结构: 主菜单(全局) -> 选择股票 -> 单个股票菜单
import json, os, sys, shutil
from datetime import datetime
from pathlib import Path

DEFAULT_SAVE_DIR = Path.home() / "AppData" / "LocalLow" / "LoneCat" / "StocksMainForceSimulator" / "Saves"

SECTOR_MAP = {
    10: "金融", 20: "科技", 30: "工业", 40: "能源",
    50: "消费", 60: "医药", 70: "交通", 80: "房产",
    90: "环保", 100: "农业"
}

BOURSE_MAP = {
    1: "上海证券交易所",
    2: "深圳证券交易所"
}
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
        except Exception: pass

def col(color, text): return color + str(text) + C.RESET
def clear(): os.system("cls" if os.name == "nt" else "clear")
def hr(c="=", w=70): print(c*w)
def pause(m="Press Enter..."): input(col(C.DIM, m))
def prompt(t, d=None):
    s = (" [" + str(d) + "]") if d is not None else ""
    v = input(col(C.CYAN, t + s + ": ")).strip()
    return v if v else d

def prompt_int(t, d=None, default=None, mn=None, mx=None):
    if default is not None and d is None:
        d = default
    while True:
        v = prompt(t, d)
        try:
            n = int(v) if v != "" else (d if d is not None else 0)
            if mn is not None and n < mn:
                print(col(C.RED, "  Err: < " + str(mn))); continue
            if mx is not None and n > mx:
                print(col(C.RED, "  Err: > " + str(mx))); continue
            return n
        except (ValueError, TypeError): print(col(C.RED, "  Err: not int"))

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
        except (ValueError, TypeError): print(col(C.RED, "  Err: not num"))

def confirm(t, no=True):
    sfx = " [y/N]" if no else " [Y/n]"
    v = input(col(C.YELLOW, t + sfx + ": ")).strip().lower()
    return (v in ("y","yes")) if v else (not no)

def find_save_dirs():
    if not DEFAULT_SAVE_DIR.exists(): return []
    return [p for p in DEFAULT_SAVE_DIR.iterdir() if p.is_dir() and any(p.glob("*.sav"))]

def list_saves(d):
    return sorted([p for p in d.iterdir() if p.suffix == ".sav" and p.is_file()])

def select_save_dir():
    ds = find_save_dirs()
    if not ds:
        print(col(C.RED, "No save dirs in " + str(DEFAULT_SAVE_DIR))); return None
    if len(ds) == 1: return ds[0]
    print(col(C.BOLD, "Save dirs:"))
    for i, d in enumerate(ds): print("  " + str(i+1) + ". " + d.name)
    return ds[prompt_int("Dir", default=1, mn=1, mx=len(ds))-1]

def select_save_file(d):
    ss = list_saves(d)
    if not ss: print(col(C.RED, "No saves")); return None
    if len(ss) == 1: return ss[0]
    print(col(C.BOLD, "Saves in " + d.name + ":"))
    for i, s in enumerate(ss):
        kb = s.stat().st_size/1024
        mt = datetime.fromtimestamp(s.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        print("  " + str(i+1) + ". " + s.name.ljust(30) + " " + str(round(kb,1)).rjust(8) + "KB  " + mt)
    return ss[prompt_int("Save", default=1, mn=1, mx=len(ss))-1]

class Editor:
    def __init__(self, path):
        self.path = Path(path)
        self.bak = self.path.with_suffix(".sav.bak." + datetime.now().strftime("%Y%m%d_%H%M%S"))
        self.data = None; self.modified = False
    def load(self):
        with open(self.path, "r", encoding="utf-8") as f: self.data = json.load(f)
        self.modified = False
        return self.data
    def save(self):
        if not self.modified: return False
        if self.path.exists(): shutil.copy2(self.path, self.bak)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, separators=(",", ":"))
        self.modified = False
        return True
    def stocks(self): return self.data.get("Market", {}).get("Stocks", [])
    def find(self, code):
        for s in self.stocks():
            if s.get("Info", {}).get("Code") == code: return s
        return None
    def codes(self): return sorted([s.get("Info", {}).get("Code") for s in self.stocks() if s.get("Info", {}).get("Code") is not None])

def fmt_p(r): return (str(round(r/100, 2)) + " Yuan") if r else "0 Yuan"
def fmt_m(r):
    """Format large numbers with billion annotation if > 50 million"""
    a = abs(r)
    if a >= 5e7:  # > 5000万
        formatted = f"{r:,}"
        yi = r / 1e8
        return f"{formatted} ({yi:.2f} 亿)"
    elif a >= 1e4:  # > 1万
        formatted = f"{r:,}"
        wan = r / 1e4
        return f"{formatted} ({wan:.2f} 万)"
    else:
        return str(r)
def show_stock(s, code=None):
    if code is None: code = s["Info"].get("Code")
    info = s["Info"]; inst = s["Institution"][0]; ret = s["Retail"][0]
    price = info["PriceFact"]; vol = info["VolumeTotal"]; rl = info["RateLimit"]
    hr()
    print(col(C.BOLD + C.CYAN, "  Stock X" + str(code)))
    hr()
    print(col(C.BOLD, "[Price 价格]"))
    print("  PriceInit 发行价:    " + str(info["PriceInit"]).rjust(15) + "  (" + fmt_p(info["PriceInit"]) + ")")
    print("  PriceFact 昨收盘:    " + str(info["PriceFact"]).rjust(15) + "  (" + fmt_p(info["PriceFact"]) + ")")
    print("  RateLimit 涨跌幅:    " + str(round(rl*100, 1)).rjust(14) + "%")
    print("  Limit 触发涨停:     " + str(info["Limit"]))
    print("  涨停:               " + str(round(info["PriceInit"]*(1+rl))).rjust(15) + "  (" + fmt_p(int(info["PriceInit"]*(1+rl))) + ")")
    print("  跌停:               " + str(round(info["PriceInit"]*(1-rl))).rjust(15) + "  (" + fmt_p(int(info["PriceInit"]*(1-rl))) + ")")
    print()
    print(col(C.BOLD, "[Company 公司信息]"))
    print("  VolumeTotal 总股本: " + str(vol))
    print("  VolumeFlow 流通股:  " + str(info["VolumeFlow"]))
    print("  Bourse 交易所:      " + str(info["Bourse"]))
    print("  Sector 板块:        " + str(info["Sector"]))
    print()
    print(col(C.BOLD, "[Finance 财务指标]"))
    np_ = info["RewardBusiness"]+info["RewardOther"]-info["CostBusiness"]-info["CostOther"]
    if vol > 0 and price > 0:
        pe = price*vol/np_ if np_ else float("inf")
        pb = price*vol/info["AssetNet"] if info["AssetNet"] else float("inf")
        print("  RewardBus 业务收益: " + str(info["RewardBusiness"]).rjust(15) + "  (" + fmt_m(info["RewardBusiness"]) + ")")
        print("  RewardOther 其他收益:" + str(info["RewardOther"]).rjust(15))
        print("  CostBus 业务成本:   " + str(info["CostBusiness"]).rjust(15))
        print("  CostOther 其他成本: " + str(info["CostOther"]).rjust(15))
        print("  NetProfit 净利润:   " + str(np_).rjust(15) + "  (" + fmt_m(np_) + ")")
        print("  AssetNet 净资产:    " + str(info["AssetNet"]).rjust(15) + "  (" + fmt_m(info["AssetNet"]) + ")")
        print("  AssetLoan 总负债:   " + str(info["AssetLoan"]).rjust(15) + "  (" + fmt_m(info["AssetLoan"]) + ")")
        d_ = info["AssetLoan"]/(info["AssetLoan"]+info["AssetNet"])*100 if (info["AssetLoan"]+info["AssetNet"]) else 0
        print("  DebtRatio 负债率:   " + str(round(d_, 2)).rjust(14) + "%")
        print("  市值 (Price*Vol):   " + str(price*vol).rjust(15) + "  (" + fmt_m(price*vol) + ")")
        if pe != float("inf") and pe != float("-inf"):
            print("  PE 市盈率 (市值/净利): " + str(round(pe, 4)).rjust(12))
        else:
            print("  PE 市盈率 (市值/净利): N/A")
        if pb != float("inf") and pb != float("-inf"):
            print("  PB 市净率 (市值/净资): " + str(round(pb, 4)).rjust(12))
        else:
            print("  PB 市净率 (市值/净资): N/A")
    print()
    print(col(C.BOLD, "[Institution 主力机构]"))
    for k, v in inst.items():
        if isinstance(v, list): print("  " + k.ljust(25) + ": list[" + str(len(v)) + "]")
        else: print("  " + k.ljust(25) + ": " + str(v))
    print()
    print(col(C.BOLD, "[Retail 散户]"))
    for k, v in ret.items(): print("  " + k.ljust(25) + ": " + str(v))
    print()
    print(col(C.BOLD, "[Last 5 candles 最近5根K线 (内部值/100=显示价)]"))
    for k in info.get("Candles", [])[-5:]:
        print("  Day " + str(k["Day"]) + ": O=" + str(round(k["Open"]/100, 2)) + " C=" + str(round(k["Close"]/100, 2)) + " H=" + str(round(k["High"]/100, 2)) + " L=" + str(round(k["Low"]/100, 2)) + " V=" + str(k["Volume"]))
    hr()

# ====== 修改函数 ======
def need_stock(e):
    code = getattr(e, "selected_code", None)
    if not code: print(col(C.RED, "  请先选股票")); pause(); return None
    s = e.find(code)
    if not s: print(col(C.RED, "  X" + str(code) + " 不存在")); pause(); return None
    return s

def change_pe(e):
    """
    修改市盈率
    
    计算公式: PE = PriceFact * VolumeTotal / NetProfit
      (即: 总市值 / 净利润)
    净利润 = RewardBusiness + RewardOther - CostBusiness - CostOther
    
    规则:
    - 目标 PE 为负数: 通过增加支出(成本)使净利润变为负
    - 目标 PE 为正数: 通过增加收入(收益)使净利润变更
    """
    import random
    s = need_stock(e)
    if not s: return
    info = s["Info"]; p = info["PriceFact"]; v = info["VolumeTotal"]
    np_ = info["RewardBusiness"]+info["RewardOther"]-info["CostBusiness"]-info["CostOther"]
    cur_pe = p*v/np_ if np_ else float("inf")
    print("  当前 PE = " + str(round(cur_pe, 4)))
    print("  PE = PriceFact * VolumeTotal / NetProfit  (市值/净利润)")
    print("  正数: 盈利 (PE越大估值越高)")
    print("  负数: 亏损 (PE越小亏损越大)")
    print()
    target = prompt_float("目标 PE (负数=亏损, 正数=盈利)", default="0.1")
    if target == 0: print(col(C.RED, "  PE 不能为 0")); pause(); return
    target_np = p*v/target
    if abs(target_np) > 1e15: print(col(C.YELLOW, "  警告: 值 > 1e15 可能有浮点精度问题"))
    
    cur_rb = info["RewardBusiness"]
    cur_ro = info["RewardOther"]
    cur_cb = info["CostBusiness"]
    cur_co = info["CostOther"]
    
    if target_np < 0:
        # 负数PE: 通过增加支出使净利润变为负
        print()
        print("  === 调整策略 (目标PE为负) ===")
        print("  通过增加业务支出和其他支出，使净利润变为负")
        print()
        
        additional_cost_needed = abs(target_np) + max(0, cur_rb + cur_ro - cur_cb - cur_co)
        additional_cost_needed = int(additional_cost_needed)
        
        # 分配到业务成本和其他成本
        ratio = random.uniform(0.6, 0.8)
        add_cost_business = int(additional_cost_needed * ratio)
        add_cost_other = additional_cost_needed - add_cost_business
        
        new_rb = cur_rb
        new_ro = cur_ro
        new_cb = cur_cb + add_cost_business
        new_co = cur_co + add_cost_other
    else:
        # 正数PE: 通过增加收入使净利润变更
        print()
        print("  === 调整策略 (目标PE为正) ===")
        print("  通过增加业务收入和其他收入，使净利润达到目标")
        print()
        
        current_np = cur_rb + cur_ro - cur_cb - cur_co
        additional_revenue_needed = target_np - current_np
        if additional_revenue_needed < 0:
            additional_revenue_needed = 0
        
        additional_revenue_needed = int(additional_revenue_needed)
        
        # 分配到业务收益和其他收益
        ratio = random.uniform(0.7, 0.9)
        add_reward_business = int(additional_revenue_needed * ratio)
        add_reward_other = additional_revenue_needed - add_reward_business
        
        new_rb = cur_rb + add_reward_business
        new_ro = cur_ro + add_reward_other
        new_cb = cur_cb
        new_co = cur_co
    
    actual_np = new_rb + new_ro - new_cb - new_co
    print("  调整前净利润: " + str(np_))
    print("  调整后净利润: " + str(actual_np))
    print()
    print("  将设置以下财务数据：")
    print("    RewardBusiness (业务收益): " + str(new_rb))
    print("    RewardOther (其他收益):    " + str(new_ro))
    print("    CostBusiness (业务成本):   " + str(new_cb))
    print("    CostOther (其他成本):     " + str(new_co))
    print("    -> 净利润 = " + str(actual_np))
    new_pe = p*v/actual_np if actual_np else float("inf")
    print("    -> 新PE = " + str(round(new_pe, 4)))
    if not confirm("确认修改?", no=False): return
    
    info["RewardBusiness"] = new_rb
    info["RewardOther"] = new_ro
    info["CostBusiness"] = new_cb
    info["CostOther"] = new_co
    info["ProfitNetPrev"] = int(actual_np)
    
    for k in ("RewardBusinessPrev", "RewardOtherPrev", "CostBusinessPrev", "CostOtherPrev"):
        if k in info:
            if "RewardBusiness" in k:
                info[k] = new_rb
            elif "RewardOther" in k:
                info[k] = new_ro
            elif "CostBusiness" in k:
                info[k] = new_cb
            elif "CostOther" in k:
                info[k] = new_co
    
    e.modified = True
    final_np = info["RewardBusiness"] + info["RewardOther"] - info["CostBusiness"] - info["CostOther"]
    print(col(C.GREEN, "  新 PE = " + str(round(p*v/final_np, 4))))
    pause()

def change_pb(e):
    s = need_stock(e)
    if not s: return
    info = s["Info"]; p = info["PriceFact"]; v = info["VolumeTotal"]
    cur_pb = p*v/info["AssetNet"] if info["AssetNet"] else float("inf")
    print("  当前 PB = " + str(round(cur_pb, 4)))
    print("  PB = PriceFact * VolumeTotal / AssetNet  (市值/净资产)")
    print("  PB < 1: 破净，股价低于净资产")
    print("  PB = 1: 正常，股价等于净资产")
    print("  PB > 1: 溢价，股价高于净资产")
    print()
    target = prompt_float("目标 PB", default="1.0", mn=0.01)
    if target == 0: print(col(C.RED, "  PB 不能为 0")); pause(); return
    target_an = p*v/target
    print("  需要设置 AssetNet = " + str(int(target_an)) + "  (使 市值/净资产 = " + str(target) + ")")
    if not confirm("确认修改?", no=False): return
    info["AssetNet"] = int(target_an)
    if "AssetNetPrev" in info: info["AssetNetPrev"] = int(target_an)
    e.modified = True
    print(col(C.GREEN, "  新 PB = " + str(round(p*v/info["AssetNet"], 4))))
    pause()

def change_debt(e):
    s = need_stock(e)
    if not s: return
    info = s["Info"]
    dr = info["AssetLoan"]/(info["AssetLoan"]+info["AssetNet"])*100 if (info["AssetLoan"]+info["AssetNet"]) else 0
    print("  当前负债率 = " + str(round(dr, 2)) + "%")
    print("  负债率 = AssetLoan / (AssetLoan + AssetNet) * 100%")
    print("  负债率越低越安全, 0% 表示完全无负债")
    print("  负债率 = 1%: 极低,几乎无负债,非常安全")
    print("  负债率 = 30%: 正常,适度负债,风险可控")
    print("  负债率 = 70%: 较高,负债较多,风险较高")
    print()
    target = prompt_float("目标负债率 % (1=极低, 30=正常, 70=较高)", default="1.0", mn=0.01, mx=99.99)
    new_loan = info["AssetNet"]*target/(100-target)
    print("  需要设置 AssetLoan = " + str(int(new_loan)))
    if not confirm("确认修改?", no=False): return
    info["AssetLoan"] = int(new_loan)
    if "AssetLoanPrev" in info: info["AssetLoanPrev"] = int(new_loan)
    e.modified = True
    new_dr = info["AssetLoan"]/(info["AssetLoan"]+info["AssetNet"])*100
    print(col(C.GREEN, "  新负债率 = " + str(round(new_dr, 2)) + "%"))
    pause()

def change_pi(e):
    s = need_stock(e)
    if not s: return
    info = s["Info"]
    print("  当前 PriceInit 发行价 = " + str(info["PriceInit"]) + " (" + fmt_p(info["PriceInit"]) + ")")
    print("  PriceInit 是涨跌停基准, 决定涨停/跌停价")
    print("  涨停 = PriceInit * (1 + RateLimit)")
    print("  跌停 = PriceInit * (1 - RateLimit)")
    print("  注意: PriceInit 是游戏内部值,显示价=PriceInit/100")
    print("  例如: PriceInit=80000 -> 显示价=800.00元")
    print()
    disp = prompt_float("新发行价 (Yuan, 显示价*100=内部值)", default=str(info["PriceInit"]/100), mn=0.01)
    raw = int(disp*100)
    print("  新涨停价 = " + str(round(raw * (1 + info["RateLimit"]))) + " (" + fmt_p(int(raw * (1 + info["RateLimit"]))) + ")")
    print("  新跌停价 = " + str(round(raw * (1 - info["RateLimit"]))) + " (" + fmt_p(int(raw * (1 - info["RateLimit"]))) + ")")
    if not confirm("确认修改?", no=False): return
    info["PriceInit"] = raw
    e.modified = True
    rl = info["RateLimit"]
    print(col(C.GREEN, "  新 limit_up=" + str(round(info["PriceInit"]*(1+rl))) + " limit_down=" + str(round(info["PriceInit"]*(1-rl)))))
    pause()

def change_pf(e):
    s = need_stock(e)
    if not s: return
    info = s["Info"]
    print("  当前 PriceFact 昨收盘 = " + str(info["PriceFact"]) + " (" + fmt_p(info["PriceFact"]) + ")")
    print("  PriceFact 是今日开盘基准, 游戏内价格从这里波动")
    print("  注意: PriceFact 是游戏内部值,显示价=PriceFact/100")
    print("  例如: PriceFact=100000 -> 显示价=1000.00元")
    print()
    disp = prompt_float("新昨收盘/开盘价 (Yuan, 显示价*100=内部值)", default=str(info["PriceFact"]/100), mn=0.01)
    raw = int(disp*100)
    if not confirm("确认修改?", no=False): return
    info["PriceFact"] = raw
    if info["Candles"]:
        info["Candles"][-1] = {"Day": info["Candles"][-1]["Day"]+1, "Open":raw, "Close":raw, "High":raw, "Low":raw, "Volume":0, "Amount":0}
    e.modified = True
    print(col(C.GREEN, "  设置为 " + str(raw) + " (" + fmt_p(raw) + ")"))
    pause()

def change_rl(e):
    s = need_stock(e)
    if not s: return
    info = s["Info"]
    print("  当前 RateLimit 涨跌幅 = " + str(round(info["RateLimit"]*100, 1)) + "%")
    print("  涨停 = PriceInit * (1 + RateLimit)")
    print("  跌停 = PriceInit * (1 - RateLimit)")
    print("  值越大波动越剧烈, 值越小越稳定")
    print("  RateLimit = 5%: 小波动,股价变化慢")
    print("  RateLimit = 10%: 默认,正常波动")
    print("  RateLimit = 20%: 大幅波动,股价变化快")
    print()
    pct = prompt_float("新涨跌停幅度 % (10=10%%默认, 20=20%%大幅波动, 5=5%%小波动)", default="10", mn=0.1, mx=100)
    print("  新涨停价 = " + str(round(info["PriceInit"] * (1 + pct/100))) + " (" + fmt_p(int(info["PriceInit"] * (1 + pct/100))) + ")")
    print("  新跌停价 = " + str(round(info["PriceInit"] * (1 - pct/100))) + " (" + fmt_p(int(info["PriceInit"] * (1 - pct/100))) + ")")
    if not confirm("确认修改?", no=False): return
    info["RateLimit"] = pct/100
    e.modified = True
    print(col(C.GREEN, "  新 RateLimit = " + str(pct) + "%"))
    pause()

def change_npc(e):
    s = need_stock(e)
    if not s: return
    inst = s["Institution"][0]; ret = s["Retail"][0]
    print(col(C.BOLD, "  当前:"))
    print("  主力可卖股数 Inst.VolSell=" + str(inst.get("VolumeUsableSell",0)) + ", Inst.AmountBuy=" + str(inst.get("AmountUsableBuy",0)))
    print("  散户可卖股数 Retail.VolSell=" + str(ret.get("VolumeUsableSell",0)) + ", Retail.AmountBuy=" + str(ret.get("AmountUsableBuy",0)))
    print()
    print("  1. 全部清零")
    print("     - 主力和散户都没有可卖的股票和可买的资金")
    print("     - 效果: 5档买卖盘全空,股票无法交易")
    print()
    print("  2. 中位数 (推荐)")
    print("     - 跟其他99只股票一样的正常水平")
    print("     - 效果: 5档有正常数量的挂单,交易正常进行")
    print()
    print("  3. 2倍中位")
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
    code = s["Info"]["Code"]
    if mode in (2,3,4):
        if mode == 2: mult = 1.0
        elif mode == 3: mult = 2
        elif mode == 4: mult = 0.5
        aubs = [x["Institution"][0].get("AmountUsableBuy",0) for x in e.stocks() if x["Info"]["Code"] != code]
        vuss = [x["Institution"][0].get("VolumeUsableSell",0) for x in e.stocks() if x["Info"]["Code"] != code]
        raubs = [x["Retail"][0].get("AmountUsableBuy",0) for x in e.stocks() if x["Info"]["Code"] != code]
        rvuss = [x["Retail"][0].get("VolumeUsableSell",0) for x in e.stocks() if x["Info"]["Code"] != code]
        def med(l):
            l = sorted(l); n = len(l)
            return l[n//2] if n%2 else (l[n//2-1]+l[n//2])/2
        inst["VolumeUsableSell"] = int(med(vuss)*mult)
        inst["AmountUsableBuy"] = int(med(aubs)*mult)
        ret["VolumeUsableSell"] = int(med(rvuss)*mult)
        ret["AmountUsableBuy"] = int(med(raubs)*mult)
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
        print("    - 当前值: " + str(inst.get("AmountUsableBuy",0)))
        print()
        print("  Retail.VolSell (散户可卖股数):")
        print("    - 散户当前持有多少股可以卖出")
        print("    - 值越大,卖单越多,股价越难涨")
        print("    - 值为-1表示无限制(游戏默认)")
        print()
        print("  Retail.AmountBuy (散户可买资金):")
        print("    - 散户有多少资金可以买入")
        print("    - 值越大,买单越多,股价越容易涨")
        print("    - 当前值: " + str(ret.get("AmountUsableBuy",0)))
        print()
        print("  === 当前值 ===")
        print("  Inst.VolSell  = " + str(inst.get("VolumeUsableSell",0)))
        print("  Inst.AmountBuy = " + str(inst.get("AmountUsableBuy",0)))
        print("  Retail.VolSell  = " + str(ret.get("VolumeUsableSell",0)))
        print("  Retail.AmountBuy = " + str(ret.get("AmountUsableBuy",0)))
        print()
        inst["VolumeUsableSell"] = prompt_int("Inst.VolSell (主力可卖股数)", default=str(inst.get("VolumeUsableSell",0)))
        inst["AmountUsableBuy"] = prompt_int("Inst.AmountBuy (主力可买资金)", default=str(inst.get("AmountUsableBuy",0)))
        ret["VolumeUsableSell"] = prompt_int("Retail.VolSell (散户可卖股数)", default=str(ret.get("VolumeUsableSell",0)))
        ret["AmountUsableBuy"] = prompt_int("Retail.AmountBuy (散户可买资金)", default=str(ret.get("AmountUsableBuy",0)))
    elif mode == 1:
        inst["VolumeUsableSell"]=0; inst["AmountUsableBuy"]=0
        ret["VolumeUsableSell"]=0; ret["AmountUsableBuy"]=0
    e.modified = True
    print(col(C.GREEN, "  已更新"))
    pause()

def change_ns(e):
    """修改市场活跃度"""
    ns = e.data["Market"]["NoticeStyle"]
    # 属性中文释义映射
    desc_map = {
        "RankRoleSize":           "龙虎榜最大人数",
        "RankCreateExchangeRate": "上排行榜需要的换手率",
        "ReportStrength":         "公告影响力 (牛/熊市)",
        "ReportCreateDay":        "业绩报告生成周期（天）",
        "NormalMarketStrength":   "市场公告影响力 (牛/熊市)",
        "NormalMarketCreateProb": "市场公告活跃度",
        "NormalMarketBuyProb":    "市场方向 (利好概率)",
        "NormalSectorStrength":   "板块公告影响力 (牛/熊市)",
        "NormalSectorCreateProb": "板块公告活跃度",
        "NormalSectorBuyProb":    "板块方向 (利好概率)",
        "NormalStockStrength":    "个股公告影响力 (牛/熊市)",
        "NormalStockCreateProb":  "个股公告活跃度",
        "NormalStockBuyProb":     "个股方向 (利好概率)",
    }
    # 活跃度级别（选项1）
    activity_levels = [
        (0.10, "极萧条"),
        (0.20, "冷清"),
        (0.36, "正常"),
        (0.55, "活跃"),
        (0.80, "沸腾"),
    ]
    # 影响力级别（选项2）
    influence_levels = [
        (1,  "极弱 (震荡市)"),
        (3,  "弱"),
        (7,  "正常"),
        (12, "强"),
        (20, "极强 (大牛市/大熊市)"),
    ]
    # 市场方向级别（选项3）
    direction_levels = [
        (0.08, "极熊 (利好极少)"),
        (0.25, "偏空"),
        (0.50, "中性"),
        (0.80, "偏多"),
        (1.00, "极牛 (全利好)"),
    ]
    while True:
        print(col(C.BOLD, "  当前市场活跃度 NoticeStyle:"))
        for k, v in ns.items():
            desc = desc_map.get(k, "")
            print("  " + k.ljust(30) + ": " + str(v) + ("  (" + desc + ")" if desc else ""))
        print()
        print("  1. 修改公告活跃度  (CreateProb, 越高公告越频繁)")
        print("  2. 牛/熊市变更   (Strength, 越高公告影响力越大)")
        print("  3. 市场方向选择  (BuyProb, 公告为利好的概率)")
        print("  4. 全部复原为默认值")
        print("  5. 自定义")
        print()
        print("  x. 返回主菜单")
        print()
        m = prompt("Mode", "1")
        if m.lower() == "x":
            return
        try:
            m = int(m)
        except ValueError:
            print(col(C.RED, "  无效输入，请输入数字 1-5 或 x"))
            pause()
            continue
        
        if m == 1:
            print("  === 公告活跃度 (同时修改 Market/Sector/Stock CreateProb) ===")
            for i, (val, name) in enumerate(activity_levels, 1):
                print("    " + str(i) + ". " + name + " = " + str(val))
            lv = prompt_int("选择级别", default=3, mn=1, mx=5)
            chosen_val, chosen_name = activity_levels[lv - 1]
            ns["NormalMarketCreateProb"] = chosen_val
            ns["NormalSectorCreateProb"] = chosen_val
            ns["NormalStockCreateProb"] = chosen_val
            print(col(C.GREEN, "  已设置公告活跃度 = " + chosen_name + " (" + str(chosen_val) + ")"))
        elif m == 2:
            print("  === 牛/熊市变更 (同时修改 Report/Market/Sector/Stock Strength) ===")
            for i, (val, name) in enumerate(influence_levels, 1):
                print("    " + str(i) + ". " + name + " = " + str(val))
            lv = prompt_int("选择级别", default=3, mn=1, mx=5)
            chosen_val, chosen_name = influence_levels[lv - 1]
            ns["ReportStrength"] = chosen_val
            ns["NormalMarketStrength"] = chosen_val
            ns["NormalSectorStrength"] = chosen_val
            ns["NormalStockStrength"] = chosen_val
            print(col(C.GREEN, "  已设置牛/熊市 = " + chosen_name + " (" + str(chosen_val) + ")"))
        elif m == 3:
            print("  === 市场方向选择 (同时修改 Market/Sector/Stock BuyProb) ===")
            for i, (val, name) in enumerate(direction_levels, 1):
                print("    " + str(i) + ". " + name + " = " + str(val))
            lv = prompt_int("选择级别", default=3, mn=1, mx=5)
            chosen_val, chosen_name = direction_levels[lv - 1]
            ns["NormalMarketBuyProb"] = chosen_val
            ns["NormalSectorBuyProb"] = chosen_val
            ns["NormalStockBuyProb"] = chosen_val
            print(col(C.GREEN, "  已设置市场方向 = " + chosen_name + " (" + str(chosen_val) + ")"))
        elif m == 4:
            # 全部复原为游戏默认值
            ns["RankRoleSize"] = 5
            ns["RankCreateExchangeRate"] = 0.3
            ns["ReportCreateDay"] = 15
            ns["ReportStrength"] = 1.0
            ns["NormalMarketStrength"] = 1.0
            ns["NormalMarketCreateProb"] = 0.08
            ns["NormalMarketBuyProb"] = 0.5
            ns["NormalSectorStrength"] = 1.0
            ns["NormalSectorCreateProb"] = 0.08
            ns["NormalSectorBuyProb"] = 0.5
            ns["NormalStockStrength"] = 1.0
            ns["NormalStockCreateProb"] = 0.02
            ns["NormalStockBuyProb"] = 0.5
            print(col(C.GREEN, "  已全部复原为游戏默认值"))
        elif m == 5:
            print("  当前值 -> 手动输入新值 (直接回车保持不变)")
            for k in list(ns.keys()):
                desc = desc_map.get(k, "")
                label = k + (" (" + desc + ")" if desc else "")
                # 整数类型: 天数、龙虎榜人数
                if k in ("ReportCreateDay", "RankRoleSize"):
                    new_v = prompt_int("  " + label + " = " + str(ns[k]) + " ->", default=str(ns[k]))
                else:
                    new_v = prompt_float("  " + label + " = " + str(ns[k]) + " ->", default=str(ns[k]))
                ns[k] = new_v
            print(col(C.GREEN, "  已更新自定义参数"))
        else:
            print(col(C.RED, "  无效选项，请输入数字 1-5"))
            pause()
            continue
        e.modified = True
        pause()


def change_player(e):
    """
    修改玩家持仓。支持循环操作，输入 x 返回主菜单。
    Code 输入为字符串，允许带 X 前缀或数字。
    """
    while True:
        print(col(C.BOLD, "  当前玩家持仓 Player.StockPos:"))
        sp = e.data["Player"]["StockPos"]
        if not sp: print("    (空)")
        for i, p in enumerate(sp):
            print("  [" + str(i) + "] Code=" + str(p.get("Code")) + " Amount=" + str(p.get("Amount")) + " Vol=" + str(p.get("VolumeUsable")))
        print("  Player.Amount (总盈亏): " + str(e.data["Player"].get("Amount", 0)))
        print()
        print("  1. 添加新持仓")
        print("  2. 修改指定Code的持仓")
        print("  3. 删除指定Code的持仓")
        print("  4. 修改Player总资金")
        print()
        print("  x. 返回主菜单")
        print()
        m = prompt("Mode", "1")
        if m.lower() == "x":
            return
        if not m.isdigit():
            print(col(C.RED, "  无效输入"))
            pause()
            continue
        m = int(m)
        
        def parse_code(s):
            s = s.strip().upper()
            if s.startswith("X"): s = s[1:]
            if s.isdigit(): return int(s)
            return None
        
        if m == 1:
            c_str = prompt("Code (如 X2075)", "")
            c = parse_code(c_str)
            if c is None:
                print(col(C.RED, "  无效代码"))
                pause()
                continue
            a = prompt_int("Amount (盈亏, 正=赚, 负=亏, 0=刚开仓)", default=0)
            v = prompt_int("VolumeUsable (可用股数)", default=0)
            sp.append({"Code": c, "Amount": a, "VolumeUsable": v})
            print(col(C.GREEN, "  已添加 Code=" + str(c)))
            e.modified = True
            pause()
        elif m == 2:
            c_str = prompt("Code (如 X2075)", "")
            c = parse_code(c_str)
            if c is None:
                print(col(C.RED, "  无效代码"))
                pause()
                continue
            found = False
            for p in sp:
                if p.get("Code") == c:
                    print("  当前: Amount=" + str(p.get("Amount", 0)) + " Vol=" + str(p.get("VolumeUsable", 0)))
                    a = prompt_int("Amount (盈亏)", default=str(p.get("Amount", 0)))
                    v = prompt_int("VolumeUsable (可用股数)", default=str(p.get("VolumeUsable", 0)))
                    p["Amount"] = a
                    p["VolumeUsable"] = v
                    found = True
                    break
            if not found:
                print(col(C.YELLOW, "  找不到 Code=" + str(c)))
            else:
                print(col(C.GREEN, "  已更新 Code=" + str(c)))
                e.modified = True
            pause()
        elif m == 3:
            c_str = prompt("Code (如 X2075)", "")
            c = parse_code(c_str)
            if c is None:
                print(col(C.RED, "  无效代码"))
                pause()
                continue
            before = len(sp)
            e.data["Player"]["StockPos"] = [p for p in sp if p.get("Code") != c]
            if len(sp) > before:
                print(col(C.GREEN, "  已删除 Code=" + str(c)))
                e.modified = True
            else:
                print(col(C.YELLOW, "  找不到 Code=" + str(c)))
            pause()
        elif m == 4:
            a = prompt_int("New Player.Amount (总盈亏)", default=str(e.data["Player"].get("Amount", 0)))
            e.data["Player"]["Amount"] = a
            e.modified = True
            print(col(C.GREEN, "  已更新总资金"))
            pause()
        else:
            print(col(C.RED, "  无效选项"))
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

# ====== 新功能：发行股票、退市、发布业绩 ======

def issue_stock(e):
    """
    发行新股票
    
    支持两种来源：
    1. 退市池B集合恢复：按标准流程发行，保留原code
    2. 自定义code：代码生成逻辑告知用户，由用户输入code
    
    股票代码生成逻辑 (对话提示，用户自行决定)：
      格式: 交易所(1位) + 板块(2位) + 序号(2位)
      例如: 1(沪) + 50(消费) + 11(序号) = 10511
      板块编码: 10金融 20科技 30工业 40能源 50消费 60医药 70交通 80房产 90环保 100农业
    
    自动计算：NetProfit、DebtRatio、PE、PB
    """
    pool = get_or_create_delisted_pool(e)
    b_set = pool["B"]
    codes = e.codes()
    
    mode = "new"
    restore_code = None
    
    print(col(C.BOLD, "  发行新股票"))
    print()
    print("  1. 从退市池B集合恢复")
    print("  2. 自定义code发行新股票（功能暂未实现）")
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
    else:
        print(col(C.RED, "  无效选项"))
        pause()
        return
        # 自定义code - 告知生成逻辑
        print()
        print(col(C.BOLD, "  === 股票代码生成逻辑 ==="))
        print("  格式: 交易所(1位) + 板块(2位) + 序号(2位)")
        print("  交易所: 1="+BOURSE_MAP[1]+"   2="+BOURSE_MAP[2])
        print("  板块: 10金融 20科技 30工业 40能源 50消费")
        print("        60医药 70交通 80房产 90环保 100农业")
        print("  示例: 1(沪) + 50(消费) + 11(序号) = 10511")
        print()
        new_code = prompt_int("自定义股票code (如 10511)", mn=1000, mx=999999)
        if new_code in codes:
            print(col(C.RED, "  X" + str(new_code) + " 已存在，请选其他code"))
            pause()
            return
        # 检查是否在 B 集合冲突也不允许
        if new_code in b_set:
            print(col(C.YELLOW, "  X" + str(new_code) + " 在退市池B集合中(冲突)"))
            pause()
            return
    
    if mode == "restore":
        new_code = restore_code
        print(col(C.GREEN, "  恢复退市股票 X" + str(new_code)))
    else:
        print(col(C.GREEN, "  发行新股票 X" + str(new_code)))
    
    print()
    
    # 根据code推断交易所和板块（用于默认值）
    bourse_from_code = str(new_code)[0] if len(str(new_code)) == 5 else ""
    sector_from_code = str(new_code)[1:3] if len(str(new_code)) == 5 else ""
    
    print("  === 股票基本信息 ===")
    price_init = prompt_float("PriceInit 发行价 (Yuan, 显示价)", default="10.0", mn=0.01)
    volume_total = prompt_int("VolumeTotal 总股本 (股数)", default="100000000", mn=1000000)
    volume_flow = prompt_int("VolumeFlow 流通股 (股数)", default=str(volume_total), mn=1)
    
    print("  Bourse 交易所选择:")
    print("    1. " + BOURSE_MAP[1])
    print("    2. " + BOURSE_MAP[2])
    default_bourse = int(bourse_from_code) if bourse_from_code in ("1", "2") else 1
    bourse = int(prompt_int("Bourse 交易所 (1=沪, 2=深)", default=default_bourse, mn=1, mx=2))
    
    print()
    print("  Sector 板块选择 (10个板块):")
    print("    1. 金融 (10)")
    print("    2. 科技 (20)")
    print("    3. 工业 (30)")
    print("    4. 能源 (40)")
    print("    5. 消费 (50)")
    print("    6. 医药 (60)")
    print("    7. 交通 (70)")
    print("    8. 房产 (80)")
    print("    9. 环保 (90)")
    print("    10. 农业 (100)")
    sector_choice_map = {1: 10, 2: 20, 3: 30, 4: 40, 5: 50, 6: 60, 7: 70, 8: 80, 9: 90, 10: 100}
    # 根据code猜默认
    default_sector = 1
    for k, v in sector_choice_map.items():
        if str(v) == sector_from_code or (len(sector_from_code) == 3 and sector_from_code.zfill(3) == str(v).zfill(3)):
            default_sector = k
            break
    sector_choice = prompt_int("Sector 板块 (1-10)", default=default_sector, mn=1, mx=10)
    sector_num = sector_choice_map[sector_choice]
    sector = int(sector_num)
    
    # 从同板块第一个股票读取Limit和RateLimit作为默认值
    sector_templates = [s for s in e.stocks() if s["Info"].get("Sector") == sector]
    template_stock = sector_templates[0] if sector_templates else None
    sector_limit = bool(template_stock["Info"].get("Limit", True)) if template_stock else True
    sector_rate_limit = template_stock["Info"].get("RateLimit", 0.1) if template_stock else 0.1
    if template_stock:
        print("  同板块模板: X" + str(template_stock["Info"]["Code"]) + "  Limit=" + str(sector_limit) + "  RateLimit=" + str(round(sector_rate_limit*100, 1)) + "%")
    else:
        print("  同板块无模板股, 使用默认: Limit=True  RateLimit=10%")
    
    print()
    print("  === 财务数据 ===")
    reward_business = prompt_int("RewardBus 业务收益", default="100000000", mn=-1000000000)
    reward_other = prompt_int("RewardOther 其他收益", default="10000000", mn=-100000000)
    cost_business = prompt_int("CostBus 业务成本", default="60000000", mn=0)
    cost_other = prompt_int("CostOther 其他成本", default="20000000", mn=0)
    
    print()
    print("  === 资产负债 ===")
    asset_net = prompt_int("AssetNet 净资产", default="500000000", mn=1000000)
    asset_loan = prompt_int("AssetLoan 总负债", default="300000000", mn=0)
    
    raw_price = int(price_init * 100)
    net_profit = reward_business + reward_other - cost_business - cost_other
    market_cap = raw_price * volume_total
    debt_ratio = asset_loan / (asset_loan + asset_net) * 100 if (asset_loan + asset_net) else 0
    pe = market_cap / net_profit if net_profit else float("inf")
    pb = market_cap / asset_net if asset_net else float("inf")
    
    print()
    print("  === 即将创建的股票数据 ===")
    print("  股票代码: X" + str(new_code))
    print("  来源: " + ("退市池B集合恢复" if mode == "restore" else "自定义"))
    print("  PriceInit 发行价:    " + fmt_p(raw_price))
    print("  VolumeTotal 总股本:  " + str(volume_total))
    print("  VolumeFlow 流通股:   " + str(volume_flow))
    print("  Bourse 交易所:       " + str(bourse))
    print("  Sector 板块:         " + str(sector))  
    print()
    print("  输入的财务数据:")
    print("  RewardBus 业务收益:  " + str(reward_business).rjust(15) + "  (" + fmt_m(reward_business) + ")")
    print("  RewardOther 其他收益:" + str(reward_other).rjust(15))
    print("  CostBus 业务成本:    " + str(cost_business).rjust(15))
    print("  CostOther 其他成本:  " + str(cost_other).rjust(15))
    print("  AssetNet 净资产:     " + str(asset_net).rjust(15) + "  (" + fmt_m(asset_net) + ")")
    print("  AssetLoan 总负债:    " + str(asset_loan).rjust(15) + "  (" + fmt_m(asset_loan) + ")")
    print()
    print("  自动计算的指标:")
    print("  NetProfit 净利润:    " + str(net_profit).rjust(15) + "  (" + fmt_m(net_profit) + ")")
    print("  DebtRatio 负债率:    " + str(round(debt_ratio, 2)).rjust(14) + "%")
    if pe != float("inf") and pe != float("-inf"):
        print("  PE 市盈率:           " + str(round(pe, 4)).rjust(14) + "  (市值/净利润)")
    else:
        print("  PE 市盈率:           N/A (净利润为0或负数)")
    if pb != float("inf") and pb != float("-inf"):
        print("  PB 市净率:           " + str(round(pb, 4)).rjust(14) + "  (市值/净资产)")
    else:
        print("  PB 市净率:           N/A (净资产为0)")
    print()
    print("  Institution.InitVolumeSell 主力初始持仓: 0 (新发行无持仓)")
    
    if not confirm("确认发行此股票?", no=False):
        return
    
    new_stock = {
        "Info": {
            "Code": new_code,
            "Limit": sector_limit,
            "RateLimit": sector_rate_limit,
            "VolumeTotal": volume_total,
            "VolumeFlow": volume_flow,
            "VolumeFlowInit": volume_flow,
            "AssetNet": asset_net,
            "AssetNetPrev": asset_net,
            "AssetLoan": asset_loan,
            "AssetLoanPrev": asset_loan,
            "RewardBusiness": reward_business,
            "RewardBusinessPrev": reward_business,
            "RewardOther": reward_other,
            "RewardOtherPrev": reward_other,
            "CostBusiness": cost_business,
            "CostBusinessPrev": cost_business,
            "CostOther": cost_other,
            "CostOtherPrev": cost_other,
            "ProfitNetPrev": net_profit,
            "PriceInit": raw_price,
            "PriceFact": raw_price,
            "Bourse": bourse,
            "Sector": sector,
            "Candles": []
        },
        "Institution": [{
            "VolumeUsableSell": 0,
            "AmountUsableBuy": 0,
            "InitVolumeSell": 0,
            "InitAmountBuy": 0,
            "Pos": [],
            "PosSell": [],
            "PosBuy": []
        }],
        "Retail": [{
            "VolumeUsableSell": 0,
            "AmountUsableBuy": 0
        }]
    }
    
    e.data["Market"]["Stocks"].append(new_stock)
    
    # 在 market.Sectors 中注册新股票code
    sectors = e.data["Market"].get("Sectors", [])
    if not isinstance(sectors, list):
        sectors = []
        e.data["Market"]["Sectors"] = sectors
    
    # 确保对应code的板块/市场对象存在，并追加code
    for sector_code in (sector, int(bourse)):
        # 查找匹配code的对象
        found = None
        for s_obj in sectors:
            if isinstance(s_obj, dict) and s_obj.get("Code") == sector_code:
                found = s_obj
                break
        if found is None:
            # 创建新对象
            found = {"Code": sector_code, "StockCodes": []}
            sectors.append(found)
        # 追加新code
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
    
    print(col(C.GREEN, "  股票 X" + str(new_code) + " 发行成功!"))
    pause()

def get_or_create_delisted_pool(e):
    """确保存档中有 DelistedPool 结构 A/B 两个集合"""
    if "DelistedPool" not in e.data["Market"] or not isinstance(e.data["Market"]["DelistedPool"], dict):
        e.data["Market"]["DelistedPool"] = {"A": [], "B": []}
    pool = e.data["Market"]["DelistedPool"]
    if "A" not in pool or not isinstance(pool["A"], list):
        pool["A"] = []
    if "B" not in pool or not isinstance(pool["B"], list):
        pool["B"] = []
    return pool

def _filter_delisted_candidates(e):
    """筛选候选：负债率>80%且最近5条业绩报告(NoticeReport)中净利润连续为负的股票"""
    ng = e.data["Market"].get("NoticeGroup", {})
    reports = ng.get("NoticeReport", []) if isinstance(ng, dict) else []
    by_code = {}
    for r in reports:
        c = r.get("Code")
        if c is None: continue
        by_code.setdefault(c, []).append(r)
    
    candidates = []
    for s in e.stocks():
        code = s["Info"].get("Code")
        info = s["Info"]
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
        print(col(C.DIM, "  以下为A集合股票，二次退市将完全删除"))
        for i in range(0, len(a_set), 10):
            print("  " + "  ".join(col(C.RED, "X" + str(c).zfill(4)) for c in a_set[i:i+10]))
        print()
        print("  输入要二次退市的股票代码 (逗号分隔，例如 1001,1002)")
        print("  直接回车跳过此步骤")
        codes_input = prompt("  二次退市", "")
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
                        price = stock["Info"].get("PriceFact", 0)
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
        print("  输入要退市的股票代码 (逗号分隔，例如 1001,1002)")
        print("  直接回车跳过")
        codes_input = prompt("  候选退市", "")
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
                info = stock["Info"]
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
        print("  输入要强制退市的股票代码 (逗号分隔，例如 1001,1002)")
        print("  直接回车取消")
        codes_input = prompt("  强制退市", "")
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
                        price = stock["Info"].get("PriceFact", 0)
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
    info = stock["Info"]
    candles = info.get("Candles", [])
    if candles:
        return candles[-1].get("Day", 0)
    return 0

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
        info = stock["Info"]
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
            codes_input = prompt("输入股票代码 (多个用逗号分隔)", "2075")
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
        info = stock["Info"]
        current_day = get_current_game_day(stock)
        notice_day = current_day + 1
        print("  当前游戏天数: " + str(current_day))
        print("  公告发布时间: Day " + str(notice_day) + " (当前+1)")
        
        # 根据 default_code 是否存在决定输入模式
        # default_code != None 表示从个股菜单进入，保持旧的绝对值输入
        # default_code == None 表示从主菜单进入，使用变化率输入
        use_change_rate = (default_code is None)
        _create_stock_performance(e, code, stock, notice_day, use_change_rate=use_change_rate)

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

def _print_notice_preview(n, label="公告"):
    """打印单条 NoticeNormal 的预览数据"""
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
    info = stock["Info"]
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
    price_fact = info.get("PriceFact", 0)
    volume_total = info.get("VolumeTotal", 0)
    market_value = price_fact * volume_total
    info["PE"] = (market_value / net_profit) if net_profit else 0
    info["PB"] = (market_value / asset_net) if asset_net else 0
    
    e.modified = True
    
    print(col(C.GREEN, "  股票业绩发布成功!"))
    print("  已添加到 NoticeGroup.NoticeReport 列表")
    print("  股票 Info 已同步更新: AssetNet / AssetLoan / RewardBusiness / RewardOther / CostBusiness / CostOther")
    print("  及计算字段 NetProfit / DebtRatio / PE / PB")
    pause()

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
    
    

# ====== 主菜单（全局操作） ======
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
        info = stock["Info"]
        price = info["PriceFact"]
        vol = info["VolumeTotal"]
        np_ = info["RewardBusiness"]+info["RewardOther"]-info["CostBusiness"]-info["CostOther"]
        pe = price*vol/np_ if np_ else float("inf")
        pb = price*vol/info["AssetNet"] if info["AssetNet"] else float("inf")
        dr = info["AssetLoan"]/(info["AssetLoan"]+info["AssetNet"])*100 if (info["AssetLoan"]+info["AssetNet"]) else 0
        
        notice_count = 0
        report_count = 0
        ng = e.data["Market"].get("NoticeGroup", {})
        if isinstance(ng, dict):
            notice_count = len([n for n in ng.get("NoticeNormal", []) if n.get("Code") == code])
            report_count = len([r for r in ng.get("NoticeReport", []) if r.get("Code") == code])
        total_notices = notice_count + report_count
        
        print(col(C.BOLD + C.CYAN, "="*70))
        print(col(C.BOLD + C.CYAN, "  Stock X" + str(code) + " Operations"))
        print(col(C.BOLD + C.CYAN, "="*70))
        print("  PriceInit 发行价:    " + fmt_p(info["PriceInit"]))
        print("  PriceFact 昨收盘:    " + fmt_p(info["PriceFact"]))
        print("  RateLimit 涨跌幅:    " + str(round(info["RateLimit"]*100, 1)) + "%")
        print("  PE 市盈率:           " + str(round(pe, 4)))
        print("  PB 市净率:           " + str(round(pb, 4)))
        print("  DebtRatio 负债率:    " + str(round(dr, 2)) + "%")
        if e.modified: print(col(C.YELLOW, "  * UNSAVED *"))
        print()
        print("  1.  Show full details          -- 查看完整详情")
        print("  2.  Change PE                  -- 改市盈率")
        print("  3.  Change PB                  -- 改市净率")
        print("  4.  Change debt ratio          -- 改负债率")
        print("  5.  Change PriceInit           -- 改发行价 (基准价)")
        print("  6.  Change PriceFact           -- 改昨收/开盘价")
        print("  7.  Change RateLimit           -- 改涨跌停幅度")
        print("  8.  Change NPC quotes          -- 改主力/散户挂单数量")
        print("  9.  View notices               -- 查看公告列表 (共" + str(total_notices) + "条)")
        print("  10. Publish notice             -- 发布公告 (针对当前股票)")
        print()
        print("  x.  Exit to main menu          -- 输入 x 返回主菜单")
        print()
        ch = prompt("Choose", "1")
        if ch.lower() == "x":
            return
        if not ch.isdigit(): continue
        ch = int(ch)
        
        if ch == 1: show_stock(stock, code); pause()
        elif ch == 2: change_pe(e)
        elif ch == 3: change_pb(e)
        elif ch == 4: change_debt(e)
        elif ch == 5: change_pi(e)
        elif ch == 6: change_pf(e)
        elif ch == 7: change_rl(e)
        elif ch == 8: change_npc(e)
        elif ch == 9: view_notices(e, code)
        elif ch == 10: publish_notice(e, default_code=code)

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
                info = stock["Info"]
                price = info["PriceFact"] / 100
                line += "  X" + str(c).zfill(4) + ": " + str(round(price, 2)).rjust(10) + " Yuan"
        print(line)

# ====== 主菜单（全局操作） ======

def main_menu(e):
    """主菜单 - 全局操作。返回值: True=完全退出程序, False=返回文件选择, None=默认"""
    while True:
        clear()
        print(col(C.BOLD + C.GREEN, "="*70))
        print(col(C.BOLD + C.GREEN, "  StocksMainForceSimulator Save Editor"))
        print(col(C.BOLD + C.GREEN, "="*70))
        print("  File: " + str(e.path))
        print("  Stocks: " + str(len(e.stocks())))
        if e.modified: print(col(C.YELLOW, "  * UNSAVED *"))
        print()
        print("                     --- Global 全局 ---")
        print()
        print("  1.  Operate single stock                    -- 操作单个股票 (进入子菜单)")
        print("  2.  Show all stocks list                    -- 查看所有股票列表")
        print("  3.  Change market activity                  -- 修改市场活跃度")
        print("  4.  Change Player.StockPos                  -- 改你的持仓")
        print()
        print("                     --- Market 市场操作 ---") 
        print()          
        print("  5.  Issue new stock                         -- 发行新股票")
        print("  6.  Delist stock                            -- 股票退市")
        print("  7.  Publish notice                          -- 发布公告")
        print()
        print("                     --- Cleanup 清理 ---")          
        print()
        print("  8.  Clear NoticeGroup                       -- 清空公告历史 (减小文件)")
        print("  9.  Trim HuddleNpc positions                -- 砍机构持仓 (提升性能)")
        print("  10. Clear Player.TradeType                  -- 清空交易历史")
        print()
        print("                     --- File 文件 ---")             
        print()
        print("  11. Save                                    -- 保存 (自动备份)")
        print("  12. Reload                                  -- 重新加载")
        print("  13. Exit                                    -- 退出")
        print()                 
        print("  x.  Back to file select                     -- 重新选择存档文件")
        print()                 
        ch = prompt("Choose", "1")
        if ch.lower() == "x":
            return False  # 返回文件选择
        if not ch.isdigit(): continue
        ch = int(ch)
        
        if ch == 1:
            # 操作单个股票
            codes = e.codes()
            if not codes:
                print(col(C.RED, "  No stocks found!"))
                pause()
                continue
            print(col(C.BOLD, "  Available stock codes:"))
            for i in range(0, len(codes), 10):
                print("  " + "  ".join("X" + str(c).zfill(4) for c in codes[i:i+10]))
            print()
            code = prompt_int("Enter stock code (e.g. 2075)", mn=1000, mx=999999)
            if e.find(code):
                stock_menu(e, code)
            else:
                print(col(C.RED, "  Stock X" + str(code) + " not found!"))
                pause()
        elif ch == 2:
            # 显示所有股票列表
            show_all_stocks(e)
            pause()
        elif ch == 3:
            change_ns(e)
        elif ch == 4:
            change_player(e)
        elif ch == 5:
            issue_stock(e)
        elif ch == 6:
            delist_stock(e)
        elif ch == 7:
            publish_notice(e)
        elif ch == 8:
            clean_ng(e)
        elif ch == 9:
            trim_hn(e)
        elif ch == 10:
            clean_tt(e)
        elif ch == 11:
            if e.save():
                print(col(C.GREEN, "  Saved!"))
            else:
                print(col(C.YELLOW, "  No changes to save"))
            pause()
        elif ch == 12:
            e.load()
            print(col(C.GREEN, "  Reloaded!"))
            pause()
        elif ch == 13:
            if e.modified:
                if confirm("存在未保存的修改，确认退出?", no=False):
                    # 用户确认退出，直接退出程序
                    print(col(C.CYAN, "  退出程序"))
                    return True
                # 用户选择"不"，返回主菜单
                print(col(C.YELLOW, "  已取消退出"))
                pause()
                continue
            return True  # 直接退出程序

def main():
    enable_ansi()
    while True:
        clear()
        print(col(C.BOLD + C.CYAN, "StocksMainForceSimulator Save Editor"))
        print()
        # 选择存档目录
        d = select_save_dir()
        if not d:
            print(col(C.YELLOW, "  未选择目录，退出"))
            pause()
            return
        # 选择存档文件
        p = select_save_file(d)
        if not p:
            print(col(C.YELLOW, "  未选择存档文件，返回"))
            pause()
            continue
        # 加载
        e = Editor(p)
        try: e.load()
        except Exception as ex:
            print(col(C.RED, "Load failed: " + str(ex))); pause(); continue
        print(col(C.GREEN, "  Loaded " + e.path.name + " (" + str(len(e.stocks())) + " stocks)"))
        pause()
        # 进入主菜单: True=完全退出, False=返回文件选择, None/其他=继续循环
        result = main_menu(e)
        if result is True:
            break  # 完全退出程序

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print(col(C.YELLOW, "Interrupted."))
    except Exception as ex:
        import traceback
        print(col(C.RED, "Error: " + str(ex)))
        traceback.print_exc()
        pause()
