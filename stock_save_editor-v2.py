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
    target = prompt_float("目标 PE (负数=亏损, 正数=盈利, 0不可用)", default="0.1")
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
    target = prompt_float("目标 PB (市值/净资产, 典型 0.5~5, >0)", default="1.0", mn=0.01)
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
    disp = prompt_float("新发行价 (显示价, 单位:元, 例如 10.00)", default=str(info["PriceInit"]/100), mn=0.01)
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
    disp = prompt_float("新昨收/开盘价 (显示价, 单位:元, 例如 10.00)", default=str(info["PriceFact"]/100), mn=0.01)
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
    print("  说明: VolumeUsableSell = 主力/散户可挂单卖出数量 (单位: 手)")
    print("        AmountUsableBuy  = 主力/散户可挂单买入金额 (单位: 元, 内部×100存储)")
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
    mode = prompt_int("选择模式 (1=全部清零, 2=中位数推荐, 3=2倍中位, 4=0.5倍缩量, 5=自定义)", default=2, mn=1, mx=5)
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
        inst["VolumeUsableSell"] = prompt_int("Inst.VolSell (主力可卖股数, 单位:手/100股)", default=str(inst.get("VolumeUsableSell",0)))
        inst["AmountUsableBuy"] = prompt_int("Inst.AmountBuy (主力可买资金, 单位:元×100)", default=str(inst.get("AmountUsableBuy",0)))
        ret["VolumeUsableSell"] = prompt_int("Retail.VolSell (散户可卖股数, 单位:手/100股, -1=无限制)", default=str(ret.get("VolumeUsableSell",0)))
        ret["AmountUsableBuy"] = prompt_int("Retail.AmountBuy (散户可买资金, 单位:元×100)", default=str(ret.get("AmountUsableBuy",0)))
    elif mode == 1:
        inst["VolumeUsableSell"]=0; inst["AmountUsableBuy"]=0
        ret["VolumeUsableSell"]=0; ret["AmountUsableBuy"]=0
    e.modified = True
    print(col(C.GREEN, "  已更新"))
    # 挂单修改后触发系统平账：确保 主力+散户+NPC+玩家 == 流通股
    try:
        _code = s["Info"]["Code"]
        _flows = int(s["Info"].get("VolumeFlow", 0))
        _inst_new = int(inst.get("VolumeUsableSell", 0))
        _ret_new = int(ret.get("VolumeUsableSell", 0))
        _npc_sum = 0
        for _k in ["AloneNpc","HuddleNpc","MessageNpc","RelayNpc","SneakNpc"]:
            for _acc in e.data["Market"].get(_k, []) or []:
                for _p in _acc.get("StockPos", []) or []:
                    if _p.get("Code") == _code:
                        _npc_sum += int(_p.get("VolumeUsable", 0))
        _player_vol = 0
        for _p in e.data["Player"].get("StockPos", []) or []:
            if _p.get("Code") == _code:
                _player_vol += int(_p.get("VolumeUsable", 0))
        _new_total = _inst_new + _ret_new + _npc_sum + _player_vol
        _delta = _new_total - _flows
        if _delta > 0:
            print(col(C.YELLOW, "  [平账] 持仓合计 > 流通股  delta=" + str(_delta) + "  依次从 主力/散户/AloneNpc 消耗, 不足则增加流通股"))
            _remain = _delta
            # 先从主力扣
            _take = min(int(inst.get("VolumeUsableSell", 0)), _remain)
            inst["VolumeUsableSell"] = int(inst.get("VolumeUsableSell", 0)) - _take; _remain -= _take
            # 再从散户扣
            _take = min(int(ret.get("VolumeUsableSell", 0)), _remain)
            ret["VolumeUsableSell"] = int(ret.get("VolumeUsableSell", 0)) - _take; _remain -= _take
            # 再从 AloneNpc 扣
            if _remain > 0:
                for _acc in e.data["Market"].get("AloneNpc", []) or []:
                    if _remain <= 0: break
                    for _p in _acc.get("StockPos", []) or []:
                        if _p.get("Code") == _code and _remain > 0:
                            _cur = int(_p.get("VolumeUsable", 0))
                            _take = min(_cur, _remain)
                            _p["VolumeUsable"] = _cur - _take; _remain -= _take
                # 写回 AloneNpc
            # 仍不够则增加流通股
            if _remain > 0:
                s["Info"]["VolumeFlow"] = int(s["Info"].get("VolumeFlow", 0)) + _remain
                if "VolumeFlowInit" in s["Info"]:
                    s["Info"]["VolumeFlowInit"] = s["Info"]["VolumeFlow"]
                print(col(C.YELLOW, "  [平账] 流通股 += " + str(_remain)))
        elif _delta < 0:
            print(col(C.YELLOW, "  [平账] 持仓合计 < 流通股  delta=" + str(_delta) + "  转移到主力持仓"))
            inst["VolumeUsableSell"] = int(inst.get("VolumeUsableSell", 0)) + (-_delta)
        if _delta != 0:
            e.modified = True
            print(col(C.GREEN, "  [平账完成] 主力=" + str(inst.get("VolumeUsableSell", 0)) + " 散户=" + str(ret.get("VolumeUsableSell", 0)) + " 流通股=" + str(s["Info"].get("VolumeFlow", 0))))
    except Exception as _ex:
        print(col(C.YELLOW, "  平账异常: " + str(_ex)))
    pause()

def change_ns(e):
    
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
        m = prompt("选择操作 (1~5, x=返回)", "1")
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
    大宗交易（盘后按现价交易）

    支持三种操作：
    1. 大宗建仓交易：建立新仓，必须当前未持有该股票
    2. 大宗股东交易：调整已持有股票的数量或成本，若持仓变为0则自动清仓
    3. 银证转账：增减玩家总资金（Amount 和 AmountInit 同步）

    所有操作保证流通股不变前提下，账户间持仓总量守恒。

    参数:
        e (Editor): Editor 实例
    返回: None
    作者: 琛ccsy
    """
    while True:
        print(col(C.BOLD, "  大宗交易 (盘后按现价交易)"))
        print()
        sp = e.data["Player"]["StockPos"]
        code_set = set()
        for p in sp:
            code_set.add(p.get("Code"))
        if sp:
            print("  当前玩家持仓:")
            for i, p in enumerate(sp):
                print("    [" + str(i) + "] Code=" + str(p.get("Code")) + " Amount=" + str(p.get("Amount")) + " Vol=" + str(p.get("VolumeUsable")))
        else:
            print("  当前玩家持仓: (空)")
        print("  Player.Amount (总资金): " + str(e.data["Player"].get("Amount", 0)))
        print("  Player.AmountInit (初始资金): " + str(e.data["Player"].get("AmountInit", 0)))
        print()
        print("  1. 大宗建仓交易 (建立新仓, 需当前未持有该股票)")
        print("  2. 大宗股东交易 (调整已持有股票, 持仓变0自动清仓)")
        print("  3. 银证转账 (资金增减, Amount与AmountInit同步)")
        print()
        print("  x. 返回主菜单")
        print()
        m = prompt("选择操作 (1~3, x=返回)", "1")
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

        def settle_stock_balance(stock_obj, delta_player_vol, reason=""):
            """
            系统平账: 保证 主力+散户+NPC+玩家 == 流通股
            
            参数:
                stock_obj (dict): 股票对象
                delta_player_vol (int): 玩家持仓变化量 (正=增加, 负=减少)
                reason (str): 操作说明
            返回: None
            作者: 琛ccsy
            """
            if not stock_obj:
                return
            info = stock_obj["Info"]
            inst = stock_obj["Institution"][0]
            ret = stock_obj["Retail"][0]
            flow = int(info.get("VolumeFlow", 0))
            inst_v = int(inst.get("VolumeUsableSell", 0))
            ret_v = int(ret.get("VolumeUsableSell", 0))
            code = info.get("Code")
            # 计算NPC合计
            npc_sum = 0
            for _k in ["AloneNpc","HuddleNpc","MessageNpc","RelayNpc","SneakNpc"]:
                for _acc in e.data["Market"].get(_k, []) or []:
                    for _p in _acc.get("StockPos", []) or []:
                        if _p.get("Code") == code:
                            npc_sum += int(_p.get("VolumeUsable", 0))
            p_vol_old = 0
            for _p in e.data["Player"].get("StockPos", []) or []:
                if _p.get("Code") == code:
                    p_vol_old += int(_p.get("VolumeUsable", 0))
            p_vol_new = p_vol_old + delta_player_vol
            total_new = inst_v + ret_v + npc_sum + p_vol_new
            delta = total_new - flow
            if delta == 0:
                return
            if delta > 0:
                print(col(C.YELLOW, "  [平账] " + reason + " 合计增加 " + str(delta) + " 手, 依次从 主力/散户/AloneNpc/其他NPC 消耗"))
                remain = delta
                # 从主力扣
                take = min(inst_v, remain)
                inst["VolumeUsableSell"] = inst_v - take; remain -= take
                # 从散户扣
                take = min(int(ret.get("VolumeUsableSell", 0)), remain)
                ret["VolumeUsableSell"] = int(ret.get("VolumeUsableSell", 0)) - take; remain -= take
                # 从 AloneNpc 扣
                if remain > 0:
                    for _acc in e.data["Market"].get("AloneNpc", []) or []:
                        if remain <= 0: break
                        for _p in _acc.get("StockPos", []) or []:
                            if _p.get("Code") == code and remain > 0:
                                _cur = int(_p.get("VolumeUsable", 0))
                                _take = min(_cur, remain); _p["VolumeUsable"] = _cur - _take; remain -= _take
                # 从其他 NPC 扣
                if remain > 0:
                    for _k in ["HuddleNpc","MessageNpc","RelayNpc","SneakNpc"]:
                        if remain <= 0: break
                        for _acc in e.data["Market"].get(_k, []) or []:
                            if remain <= 0: break
                            for _p in _acc.get("StockPos", []) or []:
                                if _p.get("Code") == code and remain > 0:
                                    _cur = int(_p.get("VolumeUsable", 0))
                                    _take = min(_cur, remain); _p["VolumeUsable"] = _cur - _take; remain -= _take
                # 仍不够则增加流通股
                if remain > 0:
                    info["VolumeFlow"] = int(info.get("VolumeFlow", 0)) + remain
                    if "VolumeFlowInit" in info:
                        info["VolumeFlowInit"] = info["VolumeFlow"]
                    print(col(C.YELLOW, "  [平账] 流通股 += " + str(remain)))
            else:
                print(col(C.YELLOW, "  [平账] " + reason + " 合计减少 " + str(-delta) + " 手, 转移到主力持仓"))
                inst["VolumeUsableSell"] = int(inst.get("VolumeUsableSell", 0)) + (-delta)
            e.modified = True

        if m == 1:
            # 大宗建仓交易
            print()
            print("  === 大宗建仓交易 ===")
            print("  说明: 建立新的玩家持仓, 要求当前玩家未持有该股票")
            print("        系统会从 主力/散户/AloneNpc/其他NPC 消耗对应数量, 保证流通股守恒")
            print("  字段含义:")
            print("    Amount = 持仓成本 (元, 内部×100存储)")
            print("    VolumeUsable = 持仓股数 (手, 1手=100股)")
            c_str = prompt("Code (如 X2075)", "")
            c = parse_code(c_str)
            if c is None:
                print(col(C.RED, "  无效代码")); pause(); continue
            if c in code_set:
                print(col(C.RED, "  玩家已持有 X" + str(c) + ", 请使用「大宗股东交易」修改"))
                pause(); continue
            stock_obj = e.find(c)
            if not stock_obj:
                print(col(C.RED, "  X" + str(c) + " 不存在")); pause(); continue
            v = prompt_int("VolumeUsable (建仓股数, 单位:手)", default=1000, mn=1)
            a = prompt_int("Amount (建仓成本, 单位:元×100)", default=int(v) * int(stock_obj["Info"].get("PriceFact", 0)))
            sp.append({"Code": c, "Amount": a, "VolumeUsable": v})
            # 同步 Optional 和 TradeType
            _opt_set = set(e.data["Player"].get("Optional", []))
            if c not in _opt_set:
                opt = e.data["Player"].get("Optional", [])
                opt.append(c); e.data["Player"]["Optional"] = opt
            tt = e.data["Player"].get("TradeType", [])
            day = get_current_game_day({"Info":{"Candles":[]}}) + 1
            tt.append({"Code": c, "Day": day, "Type": 1})
            e.data["Player"]["TradeType"] = tt
            # 系统平账
            settle_stock_balance(stock_obj, int(v), "玩家建仓 X" + str(c))
            # 大宗建仓: 玩家付钱买持仓, Amount减少, AmountInit不变
            price = int(stock_obj["Info"].get("PriceFact", 0))
            total_cost = int(v) * price
            e.data["Player"]["Amount"] = int(e.data["Player"].get("Amount", 0)) - total_cost
            print(col(C.CYAN, "  玩家总资金 Amount -= " + str(total_cost) + " (AmountInit 不变)"))
            print(col(C.GREEN, "  已建仓 X" + str(c) + " Vol=" + str(v) + " Amount=" + str(a)))
            e.modified = True
            pause()

        elif m == 2:
            # 大宗股东交易
            print()
            print("  === 大宗股东交易 ===")
            print("  说明: 调整已持有股票的数量或成本")
            print("        若持仓数量变为 0, 则自动执行清仓流程 (同步从 Optional/TradeType 移除)")
            print("        系统保证流通股守恒")
            c_str = prompt("Code (如 X2075)", "")
            c = parse_code(c_str)
            if c is None:
                print(col(C.RED, "  无效代码")); pause(); continue
            found_item = None
            for p in sp:
                if p.get("Code") == c:
                    found_item = p; break
            if found_item is None:
                print(col(C.RED, "  玩家未持有 X" + str(c) + ", 请使用「大宗建仓交易」"))
                pause(); continue
            old_vol = int(found_item.get("VolumeUsable", 0))
            old_amt = int(found_item.get("Amount", 0))
            print("  当前: Amount=" + str(old_amt) + " Vol=" + str(old_vol))
            new_v = prompt_int("新 VolumeUsable (股数, 单位:手, 0=清仓)", default=str(old_vol), mn=0)
            new_a = prompt_int("新 Amount (成本, 单位:元×100)", default=str(old_amt))
            stock_obj = e.find(c)
            delta_vol = int(new_v) - old_vol
            # 大宗股东交易: 持仓增加则Amount减少(买入), 持仓减少则Amount增加(卖出), AmountInit不变
            if delta_vol != 0 and stock_obj:
                price = int(stock_obj["Info"].get("PriceFact", 0))
                total_delta = delta_vol * price  # 正=买入(Amount-), 负=卖出(Amount+)
                e.data["Player"]["Amount"] = int(e.data["Player"].get("Amount", 0)) - total_delta
                if delta_vol > 0:
                    print(col(C.CYAN, "  买入 " + str(delta_vol) + " 手, Amount -= " + str(total_delta) + " (AmountInit 不变)"))
                else:
                    print(col(C.CYAN, "  卖出 " + str(-delta_vol) + " 手, Amount += " + str(-total_delta) + " (AmountInit 不变)"))
                settle_stock_balance(stock_obj, delta_vol, "股东交易 X" + str(c))
            # 若持仓变为 0, 执行清仓
            if int(new_v) == 0:
                e.data["Player"]["StockPos"] = [p for p in sp if p.get("Code") != c]
                # 同步 Optional 和 TradeType
                opt_list = e.data["Player"].get("Optional", [])
                e.data["Player"]["Optional"] = [x for x in opt_list if x != c]
                tt_list = e.data["Player"].get("TradeType", [])
                e.data["Player"]["TradeType"] = [t for t in tt_list if t.get("Code") != c]
                print(col(C.GREEN, "  已清仓 X" + str(c) + " Vol=" + str(old_vol)))
                if delta_vol == 0:
                    print(col(C.YELLOW, "  提示: 仅清持仓, 玩家总资金未变动"))
            else:
                found_item["Amount"] = new_a
                found_item["VolumeUsable"] = int(new_v)
                print(col(C.GREEN, "  已更新 X" + str(c) + " Amount=" + str(new_a) + " Vol=" + str(new_v)))
            e.modified = True
            pause()

        elif m == 3:
            # 银证转账
            print()
            print("  === 银证转账 ===")
            print("  说明: 增减玩家总资金, Amount 和 AmountInit 同步变更")
            print("        输入正数 = 银行转入证券 (资金增加)")
            print("        输入负数 = 证券转回银行 (资金减少)")
            cur_amt = int(e.data["Player"].get("Amount", 0))
            cur_init = int(e.data["Player"].get("AmountInit", 0))
            print("  当前: Player.Amount=" + str(cur_amt) + " AmountInit=" + str(cur_init))
            x = prompt_int("转账金额 x (单位:元×100, 正=转入, 负=转出)", default=0)
            e.data["Player"]["Amount"] = cur_amt + int(x)
            e.data["Player"]["AmountInit"] = cur_init + int(x)
            print(col(C.GREEN, "  转账完成: Amount=" + str(e.data["Player"]["Amount"]) + " AmountInit=" + str(e.data["Player"]["AmountInit"])))
            e.modified = True
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
        sector_templates = [s for s in e.stocks() if s["Info"].get("Sector") == sector_num]
        template_stock = sector_templates[0] if sector_templates else None
        sector_limit = bool(template_stock["Info"].get("Limit", True)) if template_stock else True
        sector_rate_limit = template_stock["Info"].get("RateLimit", 0.1) if template_stock else 0.1
        if template_stock:
            print("  同板块模板: X" + str(template_stock["Info"]["Code"]) + "  Limit=" + str(sector_limit) + "  RateLimit=" + str(round(sector_rate_limit*100, 1)) + "%")
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

        net_profit = reward_business + reward_other - cost_business - cost_other
        market_cap = raw_price * volume_total
        debt_ratio = asset_loan / (asset_loan + asset_net) * 100 if (asset_loan + asset_net) else 0
        pe = market_cap / net_profit if net_profit else float("inf")
        pb = market_cap / asset_net if asset_net else float("inf")

        print()
        print("  === 即将创建的股票数据 (恢复模式) ===")
        print("  股票代码: X" + str(new_code))
        print("  PriceInit 发行价:    " + fmt_p(raw_price))
        print("  VolumeTotal 总股本:  " + str(volume_total))
        print("  VolumeFlow 流通股:   " + str(volume_flow))
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
        sector_templates = [s for s in e.stocks() if s["Info"].get("Sector") == sector_num]
        template_stock = sector_templates[0] if sector_templates else None
        if template_stock:
            default_info = dict(template_stock["Info"])
            print("  同板块模板: X" + str(template_stock["Info"]["Code"]))
        else:
            default_info = {"Limit": True, "RateLimit": 0.10,
                            "AssetNet": 500000000, "AssetLoan": 300000000,
                            "RewardBusiness": 100000000, "RewardOther": 10000000,
                            "CostBusiness": 60000000, "CostOther": 20000000}

        raw_price = int(price_yuan * 100)
        inst_vol = int(floats * 0.51)
        retail_vol = floats - inst_vol
        market_cap_yuan = int(raw_price * total_shares / 100)
        inst_buy = int(market_cap_yuan * 0.51 * 100)
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
                "VolumeTotal": total_shares, "VolumeFlow": floats, "VolumeFlowInit": floats,
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
                "VolumeUsableSell": inst_vol, "AmountUsableBuy": inst_buy,
                "InitVolumeSell": inst_vol, "InitAmountBuy": inst_buy,
                "Pos": [], "PosSell": [], "PosBuy": []
            }],
            "Retail": [{"VolumeUsableSell": retail_vol, "AmountUsableBuy": retail_buy}]
        }

    # ==================== 两种模式共用: 加入股票池 & Sectors 挂接 ====================
    # 生成初始 Candles 对象 (Day=1, 价格统一为发行价)
    init_volume = max(1, int(new_stock["Info"].get("VolumeFlow", 0) * 0.01))
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

def get_or_create_delisted_pool(e):
    
    if "DelistedPool" not in e.data["Market"] or not isinstance(e.data["Market"]["DelistedPool"], dict):
        e.data["Market"]["DelistedPool"] = {"A": [], "B": []}
    pool = e.data["Market"]["DelistedPool"]
    if "A" not in pool or not isinstance(pool["A"], list):
        pool["A"] = []
    if "B" not in pool or not isinstance(pool["B"], list):
        pool["B"] = []
    return pool

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

def change_npc_all_to_retail(e):
    """
    砍机构持仓（全市场）: 遍历所有股票，将所有NPC的该股票持仓清空，合计后转入散户持仓。
    
    参数:
        e (Editor): Editor 实例
    返回: None
    异常: 无
    作者: 琛ccsy
    """
    keys = ["AloneNpc", "HuddleNpc", "MessageNpc", "RelayNpc", "SneakNpc"]
    print()
    print("  说明: 将扫描所有NPC的所有股票持仓，合计后转入对应股票的散户持仓")
    print("        会清空 AloneNpc/HuddleNpc/MessageNpc/RelayNpc/SneakNpc 的全部持仓")
    removed = {}
    for s in e.stocks():
        code = s["Info"]["Code"]
        total = 0
        for k in keys:
            for acc in e.data["Market"].get(k, []) or []:
                sp = acc.get("StockPos", []) or []
                for p in sp:
                    if p.get("Code") == code:
                        total += int(p.get("VolumeUsable", 0))
                acc["StockPos"] = [p for p in sp if p.get("Code") != code]
        if total > 0:
            removed[code] = total
    if not removed:
        print(col(C.GREEN, "  所有 NPC 无持仓可砍"))
        pause()
        return
    print(col(C.BOLD, "  砍机构明细:"))
    for c, v in removed.items():
        print("  X" + str(c) + ": " + str(v) + " 手 -> Retail.VolSell")
    if not confirm("确认执行?", no=False):
        print(col(C.DIM, "  已取消")); pause(); return
    keys_all = ["AloneNpc", "HuddleNpc", "MessageNpc", "RelayNpc", "SneakNpc"]
    for c, v in removed.items():
        st = e.find(c)
        if st:
            st["Retail"][0]["VolumeUsableSell"] = int(st["Retail"][0].get("VolumeUsableSell", 0)) + v
            # 系统平账: 保证 主力+散户+NPC+玩家 == 流通股
            # 砍机构后, 散户 += v, 其他NPC = 0, 玩家不变, 主力不变
            # 若合计 > 流通股, 依次从 散户/主力 扣减, 不够增加流通股; 若合计 < 流通股, 差额回主力
            try:
                _flow = int(st["Info"].get("VolumeFlow", 0))
                _inst = st["Institution"][0]
                _ret = st["Retail"][0]
                _iv = int(_inst.get("VolumeUsableSell", 0))
                _rv = int(_ret.get("VolumeUsableSell", 0))
                _npc_sum = 0
                for _k in keys_all:
                    for _acc in e.data["Market"].get(_k, []) or []:
                        for _p in _acc.get("StockPos", []) or []:
                            if _p.get("Code") == c:
                                _npc_sum += int(_p.get("VolumeUsable", 0))
                _p_vol = 0
                for _p in e.data["Player"].get("StockPos", []) or []:
                    if _p.get("Code") == c:
                        _p_vol += int(_p.get("VolumeUsable", 0))
                _total = _iv + _rv + _npc_sum + _p_vol
                _delta = _total - _flow
                if _delta > 0:
                    print(col(C.YELLOW, "  [平账] X" + str(c) + " 持仓合计 > 流通股  delta=" + str(_delta) + "  依次从 散户/主力 消耗, 不足则增加流通股"))
                    _remain = _delta
                    _take = min(_rv, _remain); _ret["VolumeUsableSell"] = _rv - _take; _remain -= _take
                    _take = min(int(_inst.get("VolumeUsableSell", 0)), _remain); _inst["VolumeUsableSell"] = int(_inst.get("VolumeUsableSell", 0)) - _take; _remain -= _take
                    if _remain > 0:
                        st["Info"]["VolumeFlow"] = _flow + _remain
                        if "VolumeFlowInit" in st["Info"]:
                            st["Info"]["VolumeFlowInit"] = st["Info"]["VolumeFlow"]
                        print(col(C.YELLOW, "  [平账] X" + str(c) + " 流通股 += " + str(_remain)))
                elif _delta < 0:
                    print(col(C.YELLOW, "  [平账] X" + str(c) + " 持仓合计 < 流通股  delta=" + str(_delta) + "  转移到主力持仓"))
                    _inst["VolumeUsableSell"] = int(_inst.get("VolumeUsableSell", 0)) + (-_delta)
            except Exception as _ex:
                print(col(C.YELLOW, "  平账异常 X" + str(c) + ": " + str(_ex)))
    e.modified = True
    print(col(C.GREEN, "  砍机构完成, 合计 " + str(sum(removed.values())) + " 手已转入散户"))
    pause()

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
    info = s["Info"]
    price = info.get("PriceFact", 0)
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
        vols["inst"] = int(s["Institution"][0].get("VolumeUsableSell", 0))
        vols["ret"] = int(s["Retail"][0].get("VolumeUsableSell", 0))
        for k in keys:
            v = 0
            for acc in e.data["Market"].get(k, []) or []:
                for p in acc.get("StockPos", []) or []:
                    if p.get("Code") == code:
                        v += int(p.get("VolumeUsable", 0))
            vols[k] = v
        return vols, p_entry
    def do_cash():
        vols, _ = collect_vols()
        total_hand = sum(int(v) for v in vols.values())
        max_total_by_debt = max(0, int(total_asset * 0.70) - asset_loan)
        max_total_by_asset = max(0, int(asset_net))
        max_total = min(max_total_by_debt, max_total_by_asset)
        max_D = (max_total // total_hand) if total_hand > 0 else 0
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
        total_div = total_hand * D_int
        print(col(C.BOLD, "  === 现金分红明细 ==="))
        print("  总分红=" + fmt_m(total_div) + "  max_D=" + str(round(max_D/100,2)) + " 元/手  实际 D=" + str(D))
        # 分发
        for k, vol in vols.items():
            add = int(vol) * D_int
            if add == 0: continue
            if k == "player":
                e.data["Player"]["Amount"] = int(e.data["Player"].get("Amount", 0)) + add
                e.data["Player"]["AmountInit"] = int(e.data["Player"].get("AmountInit", 0)) + add
                print("  玩家 +" + fmt_m(add))
            elif k == "inst":
                s["Institution"][0]["AmountUsableBuy"] = int(s["Institution"][0].get("AmountUsableBuy", 0)) + add
                print("  主力 +" + fmt_m(add))
            elif k == "ret":
                s["Retail"][0]["AmountUsableBuy"] = int(s["Retail"][0].get("AmountUsableBuy", 0)) + add
                print("  散户 +" + fmt_m(add))
            else:
                for acc in e.data["Market"].get(k, []) or []:
                    for p in acc.get("StockPos", []) or []:
                        if p.get("Code") == code:
                            acc["Amount"] = int(acc.get("Amount", 0)) + int(p.get("VolumeUsable", 0)) * D_int
                print("  " + k + " +" + fmt_m(add))
        new_price = max(1, int(price) - D_int)
        ratio = new_price / int(price) if price else 1
        info["PriceFact"] = new_price
        info["VolumeTotal"] = max(1, int(total_shares * ratio))
        info["VolumeFlow"] = max(1, int(flow * ratio))
        if "VolumeFlowInit" in info:
            info["VolumeFlowInit"] = info["VolumeFlow"]
        info["AssetNet"] = max(0, int(asset_net) - total_div)
        info["AssetNetPrev"] = info["AssetNet"]
        info["AssetLoanPrev"] = int(asset_loan)
        print("  新 PriceFact=" + str(new_price) + " Total=" + str(info["VolumeTotal"]) + " Flow=" + str(info["VolumeFlow"]))
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
        info["VolumeFlow"] = nf; info["VolumeTotal"] = nt; info["PriceFact"] = np2
        if "VolumeFlowInit" in info: info["VolumeFlowInit"] = nf
        # 玩家/主力/散户/NPC 持仓同比例放大
        for p in e.data["Player"].get("StockPos", []) or []:
            if p.get("Code") == code:
                old = int(p.get("VolumeUsable", 0)); p["VolumeUsable"] = int(old * r)
                if price: p["Amount"] = int(p.get("Amount", 0) * np2 / price)
        iv = int(s["Institution"][0].get("VolumeUsableSell", 0))
        s["Institution"][0]["VolumeUsableSell"] = int(iv * r)
        s["Institution"][0]["InitVolumeSell"] = s["Institution"][0]["VolumeUsableSell"]
        rv = int(s["Retail"][0].get("VolumeUsableSell", 0))
        s["Retail"][0]["VolumeUsableSell"] = int(rv * r)
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
    info = s["Info"]
    print("  定向增发说明:")
    print("    1) 发行价 = 近20日均价 × 折价率 (例如 均价10元, 折价率0.8 => 发行价8元)")
    print("    2) 玩家按发行价支付金额, 换取对应股数, 直接加入流通股")
    print("    3) 若K线不足20日, 退化为使用 PriceFact 昨收盘价作为均价")
    print()
    candles = info.get("Candles", []) or []
    last20 = candles[-20:] if len(candles) >= 20 else candles
    if not last20:
        avg20 = info.get("PriceFact", 0) / 100
    else:
        avg20 = sum(int(c.get("Close", 0)) for c in last20) / 100.0 / len(last20)
    print("  近20日均价 avg20 = " + str(round(avg20, 2)) + " 元/股 (共" + str(len(last20)) + "根K线)")
    print()
    print("  折价率说明: 0.8 = 八折 (最常见), 0.7 = 七折 (便宜), 1.0 = 不折价")
    ratio = prompt_float("折价率 (0.01~1.0, 默认0.8=八折)", default="0.8", mn=0.01, mx=1.0)
    print("  玩家支付金额: 元 (内部×100存储)")
    amt_y = prompt_float("玩家支付金额 (单位:元, 建议≥10000)", default="1000000", mn=1.0)
    py = avg20 * ratio; pi = int(py * 100)
    ns = int(amt_y / (py * 100))
    print(col(C.BOLD, "  === 定向增发明细 ==="))
    print("  X" + str(code) + " avg20=" + str(round(avg20,2)) + " ratio=" + str(ratio) + " price=" + str(round(py,2)) + " 元/股")
    print("  新增 " + str(ns) + " 手  玩家支付 " + fmt_m(int(amt_y*100)))
    if not confirm("确认定向增发?", no=False):
        return
    if ns <= 0:
        print(col(C.YELLOW, "  新增为0, 跳过")); pause(); return
    info["VolumeFlow"] = int(info.get("VolumeFlow", 0)) + ns
    info["VolumeTotal"] = int(info.get("VolumeTotal", 0)) + ns
    if "VolumeFlowInit" in info: info["VolumeFlowInit"] = info["VolumeFlow"]
    player = e.data["Player"]
    cost = int(amt_y * 100)
    player["Amount"] = int(player.get("Amount", 0)) - cost
    player["AmountInit"] = int(player.get("AmountInit", 0)) - cost
    entry = None
    for p in player.get("StockPos", []) or []:
        if p.get("Code") == code:
            entry = p; break
    if entry is None:
        entry = {"Code": code, "Amount": 0, "VolumeUsable": 0}
        player["StockPos"].append(entry)
    prev = int(entry.get("VolumeUsable", 0))
    entry["VolumeUsable"] = prev + ns
    entry["Amount"] = int(entry.get("Amount", 0)) + cost
    if prev == 0:
        opt = player.get("Optional", [])
        if code not in opt: opt.append(code)
        tt = player.get("TradeType", [])
        day = 1
        if candles: day = candles[-1].get("Day", 0) + 1
        tt.append({"Code": code, "Day": day, "Type": 1})
    e.modified = True
    print(col(C.GREEN, "  定向增发完成"))
    pause()

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

def market_rectification(e):
    """
    市场整顿: 按账户持仓比例修正使 sum_hold == VolumeFlow
    
    参数:
        e (Editor): Editor 实例
    返回: None
    作者: 琛ccsy
    """
    keys = ["AloneNpc","HuddleNpc","MessageNpc","RelayNpc","SneakNpc"]
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
    summary = {}
    for s in e.stocks():
        code = s["Info"]["Code"]
        flow = int(s["Info"].get("VolumeFlow", 0))
        inst = s["Institution"][0]; ret = s["Retail"][0]
        p_v = 0
        for p in e.data["Player"].get("StockPos", []) or []:
            if p.get("Code") == code:
                p_v += int(p.get("VolumeUsable", 0))
        iv = int(inst.get("VolumeUsableSell", 0)); rv = int(ret.get("VolumeUsableSell", 0))
        npc_v = {}
        for k in keys:
            v = 0
            for acc in e.data["Market"].get(k, []) or []:
                for p in acc.get("StockPos", []) or []:
                    if p.get("Code") == code: v += int(p.get("VolumeUsable", 0))
            npc_v[k] = v
        sh = p_v + iv + rv + sum(npc_v.values())
        diff = sh - flow
        if diff == 0:
            summary[code] = "平衡"
            continue
        if abs(diff) < 10000:
            if diff > 0:
                take = diff
                for (name, setter_fn) in [("ret", lambda v: ret.__setitem__("VolumeUsableSell", v)),
                                          ("inst", lambda v: inst.__setitem__("VolumeUsableSell", v))]:
                    cur = int(ret.get("VolumeUsableSell", 0)) if name == "ret" else int(inst.get("VolumeUsableSell", 0))
                    t = min(cur, take); setter_fn(cur - t); take -= t
                if take > 0:
                    for k in keys:
                        for acc in e.data["Market"].get(k, []) or []:
                            for p in acc.get("StockPos", []) or []:
                                if p.get("Code") == code and take > 0:
                                    cv = int(p.get("VolumeUsable", 0))
                                    t = min(cv, take); p["VolumeUsable"] = cv - t; take -= t
                if take > 0:
                    for p in e.data["Player"].get("StockPos", []) or []:
                        if p.get("Code") == code and take > 0:
                            cv = int(p.get("VolumeUsable", 0))
                            t = min(cv, take); p["VolumeUsable"] = cv - t; take -= t
                summary[code] = "顺序扣 " + str(diff - take)
            else:
                need = -diff
                inst["VolumeUsableSell"] = iv + need
                summary[code] = "主力加 " + str(need)
        else:
            if sh > 0:
                scale = flow / sh
                tot = 0
                inst["VolumeUsableSell"] = int(iv * scale); tot += inst["VolumeUsableSell"]
                ret["VolumeUsableSell"] = int(rv * scale); tot += ret["VolumeUsableSell"]
                for k in keys:
                    for acc in e.data["Market"].get(k, []) or []:
                        for p in acc.get("StockPos", []) or []:
                            if p.get("Code") == code:
                                ov = int(p.get("VolumeUsable", 0))
                                p["VolumeUsable"] = int(ov * scale); tot += int(ov * scale)
                for p in e.data["Player"].get("StockPos", []) or []:
                    if p.get("Code") == code:
                        ov = int(p.get("VolumeUsable", 0))
                        p["VolumeUsable"] = int(ov * scale); tot += int(ov * scale)
                err = flow - tot
                if err != 0:
                    for p in e.data["Player"].get("StockPos", []) or []:
                        if p.get("Code") == code:
                            p["VolumeUsable"] = int(p.get("VolumeUsable", 0)) + err
                            break
                summary[code] = "比例修正 scale=" + str(round(scale,4))
    # 兜底
    for s in e.stocks():
        code = s["Info"]["Code"]
        flow = int(s["Info"].get("VolumeFlow", 0))
        sh = int(s["Institution"][0].get("VolumeUsableSell", 0)) + int(s["Retail"][0].get("VolumeUsableSell", 0))
        for k in keys:
            for acc in e.data["Market"].get(k, []) or []:
                for p in acc.get("StockPos", []) or []:
                    if p.get("Code") == code: sh += int(p.get("VolumeUsable", 0))
        for p in e.data["Player"].get("StockPos", []) or []:
            if p.get("Code") == code: sh += int(p.get("VolumeUsable", 0))
        if sh != flow:
            s["Info"]["VolumeFlow"] = sh
            if "VolumeFlowInit" in s["Info"]: s["Info"]["VolumeFlowInit"] = sh
    e.modified = True
    print(col(C.BOLD, "  === 市场整顿明细 ==="))
    for c, r in summary.items():
        print("  X" + str(c) + ": " + str(r))
    print(col(C.GREEN, "  市场整顿完成"))
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
        print("  1.  查看完整详情            -- 显示公司价格/财务/主力/散户/K线全量数据")
        print("  2.  修改市盈率 PE            -- 通过调整业务/其他收支使 PE 变为目标值 (正=盈利, 负=亏损)")
        print("  3.  修改市净率 PB            -- 直接设定净资产 AssetNet 使 市值/净资产 = 目标 PB")
        print("  4.  修改负债率              -- 调整总负债 AssetLoan 使负债率 = 目标值 (0=无负债, 70=较高)")
        print("  5.  修改发行价 PriceInit     -- 涨跌停基准价 (显示价×100=内部值, 决定涨停/跌停)")
        print("  6.  修改昨收/开盘价 PriceFact -- 今日交易基准价 (显示价×100=内部值)")
        print("  7.  修改涨跌停幅度 RateLimit -- 波动率 (10=默认, 20=大幅波动, 5=稳定)")
        print("  8.  修改主力/散户挂单        -- VolumeUsableSell(可卖股数, 手) / AmountUsableBuy(可买资金, 元×100)")
        print("  9.  查看公告列表            -- 股票公告 NoticeNormal + 业绩报告 NoticeReport (共" + str(total_notices) + "条)")
        print("  10. 发布公告                -- 针对本股票发布 NoticeNormal/NoticeReport (利好或利空)")
        print("  11. 股票分红                -- 现金分红/送股/先送后现 (自动同步所有账户持仓)")
        print("  12. 定向增发                -- 按近20日均价×折价率发行新增流通股, 玩家认购")
        print()
        print("  x.  返回主菜单              -- 输入 x 退出当前股票菜单")
        print()
        ch = prompt("选择操作 (1~12, x=返回)", "1")
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
        elif ch == 11: stock_dividend_for_code(e, code)
        elif ch == 12: private_placement_for_code(e, code)

def show_all_stocks(e):
    
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
    
    while True:
        clear()
        print(col(C.BOLD + C.GREEN, "="*70))
        print(col(C.BOLD + C.GREEN, "  StocksMainForceSimulator Save Editor"))
        print(col(C.BOLD + C.GREEN, "="*70))
        print("  File: " + str(e.path))
        print("  Stocks: " + str(len(e.stocks())))
        if e.modified: print(col(C.YELLOW, "  * UNSAVED *"))
        print()
        print("                     --- 全局操作 ---")
        print()
        print("  1.  操作单个股票              -- 输入code进入个股菜单 (PE/PB/股价/挂单/分红/增发等)")
        print("  2.  查看所有股票列表           -- 仅展示代码与昨收价一览 (只读)")
        print("  3.  修改市场活跃度 NoticeStyle -- 调整公告频率/牛熊强度/多空倾向 (全局生效)")
        print("  4.  大宗交易                   -- 大宗建仓(Amount-) / 股东交易(买卖改Amount) / 银证转账(改Amount+AmountInit)")
        print()
        print("                     --- 市场操作 ---")
        print()
        print("  5.  发行新股票                -- 退市池B集合恢复 或 自定义code发行 (含主力51%/散户49%初始仓位)")
        print("  6.  股票退市                  -- A集合(警告,限5%涨跌停) / B集合(完全退市,清除玩家持仓)")
        print("  7.  发布公告                  -- 市场/板块/股票公告 NoticeNormal 或 业绩报告 NoticeReport")
        print("  8.  股票分红                  -- 现金分红 / 送股 / 先送后现 (自动同步全部账户)")
        print("  9.  定向增发                  -- 按近20日均价×折价率新增流通股, 玩家认购")
        print()
        print("                     --- 清理 ---")
        print()
        print("  10. 市场整顿                  -- 强制 sum_hold == VolumeFlow (差异小时按顺序扣, 差异大按比例缩放)")
        print("  11. 清空公告历史 NoticeGroup    -- 所有 NoticeNormal/NoticeReport 全部清空 (减小存档)")
        print("  12. 砍机构持仓                 -- 遍历所有NPC持仓, 转入散户 Retail.VolumeUsableSell")
        print("  13. 清空交易历史 TradeType      -- 清空 Player.TradeType 列表")
        print()
        print("                     --- 文件 ---")
        print()
        print("  14. 保存 (自动备份 .bak)       -- 将内存修改写回 .sav 文件, 原文件自动备份")
        print("  15. 重新加载                   -- 放弃内存修改, 从磁盘重新读取存档")
        print("  16. 退出                       -- 退出编辑器 (有未保存修改时会二次确认)")
        print()
        print("  x. 重新选择存档文件             -- 返回存档目录/文件选择界面")
        print()                 
        ch = prompt("选择操作 (1~16, x=重选存档)", "1")
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
            stock_dividend(e)
        elif ch == 9:
            private_placement(e)
        elif ch == 10:
            market_rectification(e)
        elif ch == 11:
            clean_ng(e)
        elif ch == 12:
            trim_hn(e)
            change_npc_all_to_retail(e)
        elif ch == 13:
            clean_tt(e)
        elif ch == 14:
            if e.save():
                print(col(C.GREEN, "  Saved!"))
            else:
                print(col(C.YELLOW, "  No changes to save"))
            pause()
        elif ch == 15:
            e.load()
            print(col(C.GREEN, "  Reloaded!"))
            pause()
        elif ch == 16:
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
