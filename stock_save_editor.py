# StocksMainForceSimulator 存档编辑器 - 终极防覆盖增强版 (完美修复保存失败问题)
# 包含：自动寻址、智能提取代码、全局修改、清理优化、自由设定财务指标、进程防覆盖、K线同步、筹码守恒与智能增发
import json, os, sys, shutil, re, subprocess
from datetime import datetime
from pathlib import Path

DEFAULT_SAVE_DIR = Path.home() / "AppData" / "LocalLow" / "LoneCat" / "StocksMainForceSimulator" / "Saves"
GAME_PROCESS_NAME = "StocksMainForceSimulator.exe"

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

# ====== 【修复】原生进程检测 (移除可能导致崩溃的 CREATE_NO_WINDOW) ======
def is_game_running():
    try:
        result = subprocess.run(f'tasklist /FI "IMAGENAME eq {GAME_PROCESS_NAME}"', 
                                capture_output=True, text=True, shell=True)
        return GAME_PROCESS_NAME.lower() in result.stdout.lower()
    except Exception: return False

def find_save_dirs(base_dir=DEFAULT_SAVE_DIR):
    base_dir = Path(base_dir)
    if not base_dir.exists(): return []
    return [p for p in base_dir.iterdir() if p.is_dir() and any(p.glob("*.sav"))]

def list_saves(d):
    return sorted([p for p in d.iterdir() if p.suffix == ".sav" and p.is_file()])

def select_save_dir(base_dir=DEFAULT_SAVE_DIR):
    base_dir = Path(base_dir)
    ds = find_save_dirs(base_dir)
    if not ds:
        print(col(C.RED, "No save dirs in " + str(base_dir))); return None
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
        
        # 【修复】保存前检测游戏是否在运行，改为“警告并允许强制保存”，不再死板拦截！
        if is_game_running():
            print(col(C.RED, "\n  ⚠️ 警告：检测到游戏进程正在后台运行！"))
            print(col(C.YELLOW, "  如果现在保存，游戏退出时的‘自动保存’可能会用内存旧数据覆盖你的修改！"))
            print(col(C.YELLOW, "  建议彻底结束游戏进程后再来保存。"))
            if not confirm("是否无视警告，强制保存？", no=True):
                return False
            
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
def fmt_v(r): return str(r)
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
        if pe != float("inf"): print("  PE 市盈率:          " + str(round(pe, 4)).rjust(14))
        if pb != float("inf"): print("  PB 市净率:          " + str(round(pb, 4)).rjust(14))
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
    s = need_stock(e)
    if not s: return
    info = s["Info"]; p = info["PriceFact"]; v = info["VolumeTotal"]
    np_ = info["RewardBusiness"]+info["RewardOther"]-info["CostBusiness"]-info["CostOther"]
    cur_pe = p*v/np_ if np_ else float("inf")
    print("  当前 PE = " + str(round(cur_pe, 4)))
    print("  PE = PriceFact * VolumeTotal / NetProfit")
    print("  PE 越小越安全, 负数表示亏损")
    print("  PE = 0.1: 极低,股票被严重低估")
    print("  PE = 1.0: 正常,股票估值合理")
    print("  PE = 10: 较高,股票可能被高估")
    print("  PE = 负数: 公司亏损,股票风险高")
    print()
    target = prompt_float("目标 PE (0.1=极小, 1=正常, 10=较大)", default="0.1")
    if target == 0: print(col(C.RED, "  PE 不能为 0")); pause(); return
    target_np = p*v/target
    if abs(target_np) > 1e15: print(col(C.YELLOW, "  警告: 值 > 1e15 可能有浮点精度问题"))
    print("  需要设置 RewardBusiness = " + str(int(target_np)))
    if not confirm("确认修改?", no=False): return
    info["RewardBusiness"] = int(target_np); info["RewardOther"]=0
    info["CostBusiness"]=0; info["CostOther"]=0; info["ProfitNetPrev"]=int(target_np)
    for k in ("RewardBusinessPrev","RewardOtherPrev","CostBusinessPrev","CostOtherPrev"):
        if k in info: info[k] = int(target_np) if "Reward" in k else 0
    for k in ("RewardBusinessMin","RewardOtherMin","CostBusinessMin","CostOtherMin"):
        if k in info: info[k] = 0
    e.modified = True
    new_np = info["RewardBusiness"]+info["RewardOther"]-info["CostBusiness"]-info["CostOther"]
    print(col(C.GREEN, "  新 PE = " + str(round(p*v/new_np, 4))))
    pause()

def change_pb(e):
    s = need_stock(e)
    if not s: return
    info = s["Info"]; p = info["PriceFact"]; v = info["VolumeTotal"]
    cur_pb = p*v/info["AssetNet"] if info["AssetNet"] else float("inf")
    print("  当前 PB = " + str(round(cur_pb, 4)))
    print("  PB = PriceFact * VolumeTotal / AssetNet")
    print("  PB < 1 表示净资产相对股价高, PB > 1 表示净资产相对股价低")
    print("  PB = 0.1: 极低,股价远低于净资产")
    print("  PB = 1.0: 正常,股价等于净资产")
    print("  PB = 10: 较高,股价远高于净资产")
    print()
    target = prompt_float("目标 PB (0.1=极小, 1=正常, 10=较大)", default="0.1")
    if target == 0: print(col(C.RED, "  PB 不能为 0")); pause(); return
    target_an = p*v/target
    print("  需要设置 AssetNet = " + str(int(target_an)))
    if not confirm("确认修改?", no=False): return
    info["AssetNet"] = int(target_an)
    if "AssetNetPrev" in info: info["AssetNetPrev"] = int(target_an)
    if "AssetNetMin" in info: info["AssetNetMin"] = 0
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
    if "AssetLoanMin" in info: info["AssetLoanMin"] = 0
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
    
    # 【增强】K线强制同步：确保游戏内‘最新价’和‘总市值’立刻改变
    if info.get("Candles") and len(info["Candles"]) > 0:
        last = info["Candles"][-1]
        last["Close"] = raw
        last["Open"] = raw
        if "High" in last and last["High"] < raw: last["High"] = raw
        if "Low" in last and last["Low"] > raw: last["Low"] = raw
    else:
        info["Candles"] = [{"Day": 1, "Open":raw, "Close":raw, "High":raw, "Low":raw, "Volume":0, "Amount":0}]
        
    e.modified = True
    print(col(C.GREEN, "  设置为 " + str(raw) + " (" + fmt_p(raw) + ")，K线已强制同步！"))
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
    code = s["Info"]["Code"]
    if mode in (2,3,4):
        if mode == 2: mult = 1.0
        elif mode == 3: mult = 1.5
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

def change_financials(e):
    """直接修改所有财务指标（自由设定数值）"""
    s = need_stock(e)
    if not s: return
    info = s["Info"]
    
    clear()
    print(col(C.BOLD + C.CYAN, "="*70))
    print(col(C.BOLD + C.CYAN, "  自由设定财务指标 (Change Financials Freely)"))
    print(col(C.BOLD + C.CYAN, "="*70))
    
    print(col(C.BOLD, "\n  当前基础财务数据:"))
    print("  总股本 (VolumeTotal):      " + fmt_m(info.get("VolumeTotal", 0)))
    print("  流通股 (VolumeFlow):       " + fmt_m(info.get("VolumeFlow", 0)))
    print("  净资产 (AssetNet):         " + fmt_m(info.get("AssetNet", 0)))
    print("  总负债 (AssetLoan):        " + fmt_m(info.get("AssetLoan", 0)))
    print("  业务收益 (RewardBusiness): " + fmt_m(info.get("RewardBusiness", 0)))
    print("  其他收益 (RewardOther):    " + fmt_m(info.get("RewardOther", 0)))
    print("  业务成本 (CostBusiness):   " + fmt_m(info.get("CostBusiness", 0)))
    print("  其他成本 (CostOther):      " + fmt_m(info.get("CostOther", 0)))
    print()
    print(col(C.YELLOW, "  * 提示：支持输入 '1000000' 或 '100万' 或 '5亿'，程序会自动转换！"))
    print(col(C.YELLOW, "  * 直接按 Enter 保持原值不变。"))
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
    ns = e.data["Market"]["NoticeStyle"]
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
    if m == 1:
        ns["NormalStockStrength"] = 2.0; ns["NormalStockCreateProb"] = 0.5
        print(col(C.GREEN, "  已推高个股买入力度"))
    elif m == 2:
        ns["NormalSectorStrength"] = 1.5
        print(col(C.GREEN, "  已推高板块买入力度"))
    elif m == 3:
        ns["NormalSectorStrength"] = 0.5; ns["NormalSectorCreateProb"] = 0.0
        print(col(C.GREEN, "  已设置板块下跌"))
    elif m == 4:
        ns["NormalStockStrength"] = 0.5; ns["NormalStockCreateProb"] = 0.0
        print(col(C.GREEN, "  已设置个股下跌"))
    elif m == 5:
        ns["NormalMarketStrength"]=1.0; ns["NormalMarketCreateProb"]=0.0
        ns["NormalSectorStrength"]=1.0; ns["NormalSectorCreateProb"]=0.0
        ns["NormalStockStrength"]=1.0; ns["NormalStockCreateProb"]=0.0
        print(col(C.GREEN, "  已全部复原"))
    elif m == 6:
        print("  当前值 -> 手动输入新值 (直接回车保持不变)")
        for k in list(ns.keys()):
            if k in ("RankCreateExchangeRate","ReportCreateDay"):
                ns[k] = prompt_int("  " + k + " = " + str(ns[k]) + " ->", default=str(ns[k]))
            else:
                ns[k] = prompt_float("  " + k + " = " + str(ns[k]) + " ->", default=str(ns[k]))
    e.modified = True
    pause()

# ====== 【核心新增】智能增发扩股函数 (维持估值与股价不变) ======
def dilute_stock_for_shortage(stock, shortage):
    """
    当玩家买入量超过NPC可用筹码时，触发定向增发。
    同比例扩大总股本、流通股，并等比例放大所有财务指标，确保PE/PB和每股数据完全不变。
    """
    info = stock["Info"]
    old_total = info.get("VolumeTotal", 1)
    if old_total <= 0: old_total = 1
    
    new_total = old_total + shortage
    multiplier = new_total / old_total
    
    print(col(C.YELLOW, f"  ⚠️ 筹码不足，触发定向增发机制！"))
    print(col(C.YELLOW, f"  增发数量: {shortage:,} 股 | 扩容比例: {multiplier:.4f} 倍"))
    
    # 1. 扩大股本
    info["VolumeTotal"] = int(new_total)
    info["VolumeFlow"] = info.get("VolumeFlow", 0) + shortage
    
    # 2. 等比例放大财务指标 (维持每股净资产、每股收益不变 -> 维持PB/PE不变)
    finance_keys = [
        "AssetNet", "AssetLoan", 
        "RewardBusiness", "RewardOther", "CostBusiness", "CostOther",
        "AssetNetPrev", "AssetLoanPrev", 
        "RewardBusinessPrev", "RewardOtherPrev", "CostBusinessPrev", "CostOtherPrev",
        "ProfitNetPrev"
    ]
    for k in finance_keys:
        if k in info:
            info[k] = int(info[k] * multiplier)
            
    # Min字段保持0或同比例放大（这里选择保持0，因为Min通常代表历史最低，放大不影响当前逻辑）
    # 如果有其他需要放大的字段，可在此补充

# ====== 【核心升级】玩家持仓修改 (带全局筹码视野与NPC同步过户及智能增发) ======
def change_player(e):
    print(col(C.BOLD, "  当前玩家持仓 Player.StockPos:"))
    sp = e.data["Player"]["StockPos"]
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
            
        info = stock["Info"]
        inst = stock.get("Institution", [{}])[0]
        ret = stock.get("Retail", [{}])[0]
        hot = stock.get("HotMoney", [{}])[0] if "HotMoney" in stock and stock["HotMoney"] else {}
        
        # 1. 显示全局筹码视野
        hr("-", 50)
        print(col(C.BOLD + C.CYAN, "  [X" + str(c) + " 筹码分布全景]"))
        print("  总股本 (VolumeTotal): " + col(C.YELLOW, fmt_m(info.get("VolumeTotal", 0))))
        print("  流通股 (VolumeFlow):  " + col(C.YELLOW, fmt_m(info.get("VolumeFlow", 0))))
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
        info = stock["Info"]
        price = info["PriceFact"]
        vol = info["VolumeTotal"]
        np_ = info["RewardBusiness"]+info["RewardOther"]-info["CostBusiness"]-info["CostOther"]
        pe = price*vol/np_ if np_ else float("inf")
        pb = price*vol/info["AssetNet"] if info["AssetNet"] else float("inf")
        dr = info["AssetLoan"]/(info["AssetLoan"]+info["AssetNet"])*100 if (info["AssetLoan"]+info["AssetNet"]) else 0
        
        print(col(C.BOLD + C.CYAN, "="*70))
        print(col(C.BOLD + C.CYAN, "  Stock X" + str(code) + " Operations"))
        print(col(C.BOLD + C.CYAN, "="*70))
        print("  PriceInit 发行价:    " + fmt_p(info["PriceInit"]))
        print("  PriceFact 昨收盘:    " + fmt_p(info["PriceFact"]))
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
        print("  0.  Back to main menu      -- 返回主菜单")
        print()
        ch = prompt("Choose", "1")
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
        elif ch == 9: change_financials(e)
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
                info = stock["Info"]
                price = info["PriceFact"] / 100
                line += "  X" + str(c).zfill(4) + ": " + str(round(price, 2)).rjust(10) + " Yuan"
        print(line)

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
        print("  --- Cleanup 清理 ---")
        print("  5.  Clear NoticeGroup       -- 清空公告历史 (减小文件)")
        print("  6.  Trim HuddleNpc positions -- 砍机构持仓 (提升性能)")
        print("  7.  Clear Player.TradeType  -- 清空交易历史")
        print("  --- File 文件 ---")
        print("  8.  Save                    -- 保存 (带进程防覆盖检测)")
        print("  9.  Reload                  -- 重新加载")
        print("  10. Exit                    -- 退出")
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
        elif ch == 5: clean_ng(e)
        elif ch == 6: trim_hn(e)
        elif ch == 7: clean_tt(e)
        elif ch == 8:
            if e.save(): print(col(C.GREEN, "  Saved! (存档已安全写入)"))
            else: print(col(C.YELLOW, "  No changes to save (或取消保存)"))
            pause()
        elif ch == 9:
            e.load()
            print(col(C.GREEN, "  Reloaded!"))
            pause()
        elif ch == 10:
            if e.modified and not confirm("Unsaved changes, exit?", no=True):
                continue
            return

def parse_args(argv=None):
    import argparse
    p = argparse.ArgumentParser(
        prog="stock_save_editor.py",
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