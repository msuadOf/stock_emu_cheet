"""pytauri 命令层：前端 ``pyInvoke`` 调用的入口，转调 ``src.core``。

设计：每个命令接收单个 ``body`` 参数（前端 ``pyInvoke(cmd, {...})`` 传的整个对象），
从 body 取字段 → 打开存档 → 执行 core 操作 → 按需写回 → 返回 dict。

注意：pytauri 的 ``@commands.command()`` 只允许参数名为
``body``/``app_handle``/``webview_window``/``headers`` 或 ``Annotated``，
裸参数名（如 ``file``/``code``）会报错。所以这里统一用 ``body: dict``。
"""
from pathlib import Path

from pytauri import Commands

from src.core import (
    load_json, write_json_compact,
    stocks_of, find_stock, codes_of,
    calc_pe, calc_pb, calc_market_cap,
    set_target_pe, set_target_pb, set_target_debt_ratio,
    set_price_init, set_price_fact_sync_candles, set_rate_limit,
)
from src.core.extra import (
    rectify_market, move_npc_to_retail,
    delist_to_a, delist_to_b,
    apply_cash_dividend, apply_stock_dividend, cash_dividend_limits,
    compute_placement, apply_private_placement,
)


# ---- 轻量 Editor 替身（只满足 core 额外函数对 e 的最小接口）----
class _SaveCtx:
    """持存档 dict 并暴露 core 额外函数期望的 e.data / e.find / e.stocks / e.modified。"""

    def __init__(self, data):
        self.data = data
        self.modified = False

    def find(self, code):
        return find_stock(self.data, code)

    def stocks(self):
        return stocks_of(self.data)


def _stock_summary(info, code):
    """把某只股票 Info 转成前端友好的 dict。"""
    pe = calc_pe(info)
    pb = calc_pb(info)
    return {
        "code": code,
        "price_init": info.get("PriceInit", 0),
        "price_fact": info.get("PriceFact", 0),
        "rate_limit": info.get("RateLimit", 0),
        "volume_total": info.get("VolumeTotal", 0),
        "volume_flow": info.get("VolumeFlow", 0),
        "market_cap": int(calc_market_cap(info)),
        "pe": None if pe == float("inf") else round(pe, 4),
        "pb": None if pb == float("inf") else round(pb, 4),
    }


commands = Commands()


# ------------------------------------------------------------------
# 主干命令（body 是前端 pyInvoke 传的整个参数对象）
# ------------------------------------------------------------------
@commands.command()
async def list_stocks(body: dict) -> dict:
    """列出存档所有股票的概况。body: {file}"""
    file = body["file"]
    data = load_json(file)
    out = []
    for code in codes_of(data):
        stock = find_stock(data, code)
        if stock:
            out.append(_stock_summary(stock["Info"], code))
    return {"stocks": out, "count": len(out)}


@commands.command()
async def get_stock(body: dict) -> dict:
    """取单只股票详情。body: {file, code}"""
    data = load_json(body["file"])
    code = body["code"]
    stock = find_stock(data, code)
    if stock is None:
        return {"error": f"X{code} 不存在"}
    return _stock_summary(stock["Info"], code)


@commands.command()
async def set_pe(body: dict) -> dict:
    """body: {file, code, target, save?}"""
    file, code, target = body["file"], body["code"], body["target"]
    save = body.get("save", True)
    if target == 0:
        return {"error": "PE 不能为 0"}
    data = load_json(file)
    info = find_stock(data, code)["Info"]
    set_target_pe(info, target)
    if save:
        write_json_compact(file, data)
    return _stock_summary(info, code)


@commands.command()
async def set_pb(body: dict) -> dict:
    """body: {file, code, target, save?}"""
    file, code, target = body["file"], body["code"], body["target"]
    save = body.get("save", True)
    data = load_json(file)
    info = find_stock(data, code)["Info"]
    set_target_pb(info, target)
    if save:
        write_json_compact(file, data)
    return _stock_summary(info, code)


@commands.command()
async def set_debt(body: dict) -> dict:
    """body: {file, code, ratio_pct, save?}"""
    file, code = body["file"], body["code"]
    ratio_pct = body["ratio_pct"]
    save = body.get("save", True)
    data = load_json(file)
    info = find_stock(data, code)["Info"]
    set_target_debt_ratio(info, ratio_pct)
    if save:
        write_json_compact(file, data)
    return _stock_summary(info, code)


@commands.command()
async def set_price(body: dict) -> dict:
    """body: {file, code, yuan, field?('init'|'fact'), save?}"""
    file, code = body["file"], body["code"]
    yuan = body["yuan"]
    field = body.get("field", "fact")
    save = body.get("save", True)
    data = load_json(file)
    info = find_stock(data, code)["Info"]
    raw = int(yuan * 100)
    if field == "init":
        set_price_init(info, raw)
    else:
        set_price_fact_sync_candles(info, raw)
    if save:
        write_json_compact(file, data)
    return _stock_summary(info, code)


@commands.command()
async def set_ratelimit(body: dict) -> dict:
    """body: {file, code, pct, save?}"""
    file, code = body["file"], body["code"]
    pct = body["pct"]
    save = body.get("save", True)
    data = load_json(file)
    info = find_stock(data, code)["Info"]
    set_rate_limit(info, pct)
    if save:
        write_json_compact(file, data)
    return _stock_summary(info, code)


@commands.command()
async def save_file(body: dict) -> dict:
    """body: {file}（GUI 总是按用户确认结果决定是否保存，这里直接写）。"""
    file = body["file"]
    data = load_json(file)
    write_json_compact(file, data)
    return {"saved": file}


# ------------------------------------------------------------------
# extra 命令（[extra] 标注）
# ------------------------------------------------------------------
# [extra] 市场整顿：强制筹码守恒
@commands.command()
async def rectify(body: dict) -> dict:
    """body: {file, save?}"""
    file = body["file"]
    save = body.get("save", True)
    data = load_json(file)
    ctx = _SaveCtx(data)
    summary = rectify_market(ctx)
    if save and ctx.modified:
        write_json_compact(file, data)
    return {"summary": {str(k): v for k, v in summary.items()}}


# [extra] 砍机构持仓转散户
@commands.command()
async def npc_to_retail(body: dict) -> dict:
    """body: {file, save?}"""
    file = body["file"]
    save = body.get("save", True)
    data = load_json(file)
    ctx = _SaveCtx(data)
    moved = move_npc_to_retail(ctx)
    if save and ctx.modified:
        write_json_compact(file, data)
    return {"moved": {str(k): v for k, v in moved.items()}}


# [extra] 退市（默认进 A 集合警告；to_b=True 完全退市）
@commands.command()
async def delist(body: dict) -> dict:
    """body: {file, code, to_b?, save?}"""
    file, code = body["file"], body["code"]
    to_b = body.get("to_b", False)
    save = body.get("save", True)
    data = load_json(file)
    ctx = _SaveCtx(data)
    if to_b:
        stock, positions = delist_to_b(ctx, code)
        result = {"mode": "b", "removed_positions": len(positions)}
    else:
        ok = delist_to_a(ctx, code)
        result = {"mode": "a", "ok": ok}
    if save and ctx.modified:
        write_json_compact(file, data)
    return result


# [extra] 分红（cash=每手元/100股，stock_gift=10送X；二者可同时）
@commands.command()
async def dividend(body: dict) -> dict:
    """body: {file, code, cash?, stock_gift?, save?}"""
    file, code = body["file"], body["code"]
    cash = body.get("cash")
    stock_gift = body.get("stock_gift")
    save = body.get("save", True)
    data = load_json(file)
    ctx = _SaveCtx(data)
    stock = find_stock(data, code)
    result = {}
    if stock_gift is not None:
        apply_stock_dividend(ctx, code, stock, stock_gift)
        result["stock_gift"] = stock_gift
    if cash is not None:
        vols = {"player": 0, "inst": stock["Institution"][0].get("VolumeUsableSell", 0),
                "ret": stock["Retail"][0].get("VolumeUsableSell", 0)}
        D_int = int(cash * 100)
        max_total, max_D = cash_dividend_limits(stock["Info"], sum(vols.values()))
        if D_int > max_D:
            return {"error": f"每手分红 {cash} 超过上限 {round(max_D/100,2)}"}
        total = apply_cash_dividend(ctx, code, stock, vols, D_int)
        result["cash_total"] = total
    if save and ctx.modified:
        write_json_compact(file, data)
    return result


# [extra] 定向增发（ratio=折价率，amount=玩家支付元）
@commands.command()
async def placement(body: dict) -> dict:
    """body: {file, code, ratio?, amount?, save?}"""
    file, code = body["file"], body["code"]
    ratio = body.get("ratio", 0.8)
    amount = body.get("amount", 1_000_000)
    save = body.get("save", True)
    data = load_json(file)
    ctx = _SaveCtx(data)
    stock = find_stock(data, code)
    candles = stock["Info"].get("Candles", []) or []
    avg20, py, pi, ns, cost = compute_placement(candles, stock["Info"].get("PriceFact", 0),
                                                ratio, amount)
    if ns <= 0:
        return {"error": "新增为 0"}
    apply_private_placement(ctx, code, stock, ns, cost, candles)
    if save and ctx.modified:
        write_json_compact(file, data)
    return {"new_shares": ns, "cost": cost, "issue_price": round(py, 2)}
