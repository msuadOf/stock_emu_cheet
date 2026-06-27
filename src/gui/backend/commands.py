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
    default_save_dir, list_save_slots, list_save_files,
    batch_set_npc_quotes, batch_set_notice_style, batch_set_player_pct,
)
from src.core.extra import (
    rectify_market, move_npc_to_retail,
    delist_to_a, delist_to_b,
    collect_dividend_vols,
    apply_cash_dividend, apply_stock_dividend, cash_dividend_limits,
    compute_placement, apply_private_placement,
)
from src.core.savemodel import SaveModel


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
# 存档定位（默认目录 + 槽列表 + 文件列表，供前端做选择器）
# ------------------------------------------------------------------
@commands.command()
async def get_default_save(body: dict) -> dict:
    """返回默认存档根目录路径。body 可为空 dict。"""
    return {"default_dir": str(default_save_dir())}


@commands.command()
async def list_slots(body: dict) -> dict:
    """列出默认(或 body.dir 指定)目录下的存档槽。

    body: {} 或 {"dir": "..."}. 返回 {"slots": [{name, path, file_count}, ...]}.
    """
    base = body.get("dir") or str(default_save_dir())
    return {"slots": list_save_slots(base)}


@commands.command()
async def list_files(body: dict) -> dict:
    """列出某存档目录下的 .sav 文件，供用户选择。

    body: {"dir": "..."}. 返回 {"files": [{name, path, size_kb, modified}, ...]}.
    """
    return {"files": list_save_files(body["dir"])}


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
# 批量操作（对一组股票统一设置）
# ------------------------------------------------------------------
@commands.command()
async def batch_player_pct(body: dict) -> dict:
    """批量持仓：把玩家对一组股票的持仓设为各自流通股的 pct%。

    body: {file, codes:[int], pct:float(0-100), target?:'inst'|'ret'|'hot', save?}
    带筹码守恒（target 缺省 'inst'）；筹码不足会触发增发（action='diluted'）。
    """
    file = body["file"]
    codes = body["codes"]
    pct = body["pct"]
    target = body.get("target", "inst")
    save = body.get("save", True)
    data = load_json(file)
    save_model = SaveModel.from_dict(data)
    results = batch_set_player_pct(save_model, codes, pct, target_account=target)
    if save:
        write_json_compact(file, data)
    # 返回时 key 转 str（JSON 要求）
    return {"results": {str(k): v for k, v in results.items()},
            "count": len(results)}


@commands.command()
async def batch_npc_quotes(body: dict) -> dict:
    """批量设主力/散户挂单（愿意购入资金 / 卖压）。

    body: {file, codes:[int], amount_buy?:int|null, volume_sell?:int|null,
           apply_inst?:bool, apply_ret?:bool, save?}
    """
    file = body["file"]
    data = load_json(file)
    save_model = SaveModel.from_dict(data)
    results = batch_set_npc_quotes(
        save_model, body["codes"],
        amount_buy=body.get("amount_buy"),
        volume_sell=body.get("volume_sell"),
        apply_inst=body.get("apply_inst", True),
        apply_ret=body.get("apply_ret", True),
    )
    if body.get("save", True):
        write_json_compact(file, data)
    return {"results": {str(k): v for k, v in results.items()},
            "count": len(results)}


@commands.command()
async def batch_notice_style(body: dict) -> dict:
    """批量设 NPC 购买取向（NoticeStyle 个股级参数，全局生效）。

    body: {file, codes:[int], strength?:float|null, create_prob?:float|null, save?}
    """
    file = body["file"]
    data = load_json(file)
    save_model = SaveModel.from_dict(data)
    result = batch_set_notice_style(
        save_model, body["codes"],
        strength=body.get("strength"),
        create_prob=body.get("create_prob"),
    )
    if body.get("save", True):
        write_json_compact(file, data)
    return result


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
    save_model = SaveModel.from_dict(data)
    summary = rectify_market(save_model)
    if save:
        write_json_compact(file, data)
    return {"summary": {str(k): v for k, v in summary.items()}}


# [extra] 砍机构持仓转散户
@commands.command()
async def npc_to_retail(body: dict) -> dict:
    """body: {file, save?}"""
    file = body["file"]
    save = body.get("save", True)
    data = load_json(file)
    save_model = SaveModel.from_dict(data)
    moved = move_npc_to_retail(save_model)
    if save:
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
    save_model = SaveModel.from_dict(data)
    if to_b:
        stock, positions = delist_to_b(save_model, code)
        result = {"mode": "b", "removed_positions": len(positions)}
    else:
        ok = delist_to_a(save_model, code)
        result = {"mode": "a", "ok": ok}
    if save:
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
    save_model = SaveModel.from_dict(data)
    stock = save_model.find(code)
    result = {}
    if stock_gift is not None:
        apply_stock_dividend(save_model, code, stock, stock_gift)
        result["stock_gift"] = stock_gift
    if cash is not None:
        vols = collect_dividend_vols(save_model, code, stock)
        D_int = int(cash * 100)
        max_total, max_D = cash_dividend_limits(stock.info, sum(vols.values()))
        if D_int > max_D:
            return {"error": f"每手分红 {cash} 超过上限 {round(max_D/100,2)}"}
        total = apply_cash_dividend(save_model, code, stock, vols, D_int)
        result["cash_total"] = total
    if save:
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
    save_model = SaveModel.from_dict(data)
    stock = save_model.find(code)
    candles = stock.info._d.get("Candles", []) or []
    avg20, py, pi, ns, cost = compute_placement(candles, stock.info.price_fact_raw,
                                                ratio, amount)
    if ns <= 0:
        return {"error": "新增为 0"}
    apply_private_placement(save_model, code, stock, ns, cost, candles)
    if save:
        write_json_compact(file, data)
    return {"new_shares": ns, "cost": cost, "issue_price": round(py, 2)}
