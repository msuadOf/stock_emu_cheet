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
    stocks_of, codes_by_sector,
    calc_pe, calc_pb, calc_market_cap,
    set_target_pe, set_target_pb, set_target_debt_ratio,
    set_price_init, set_price_fact_sync_candles, set_rate_limit,
    apply_financial_fields, apply_notice_style,
    set_npc_quotes_by_median, set_npc_quotes_custom, clear_npc_quotes,
    add_player_position, modify_player_position, delete_player_position, set_player_amount,
    clear_notice_group, clear_trade_type, trim_huddle_npc,
    default_save_dir, list_save_slots, list_save_files,
    batch_set_npc_quotes, batch_set_notice_style, batch_set_player_pct,
)
from src.core.extra import (
    rectify_market, move_npc_to_retail,
    delist_to_a, delist_to_b,
    collect_dividend_vols,
    apply_cash_dividend, apply_stock_dividend, cash_dividend_limits,
    compute_placement, apply_private_placement,
    build_stock_notice, append_notice_normal,
    build_performance_report, commit_performance_report,
)
from src.core.savemodel import SaveModel


def _stock_summary(info, code):
    """把某只股票 Info 转成前端友好的 dict。info: InfoModel（用访问器，禁裸 dict）。"""
    pe = calc_pe(info._d)
    pb = calc_pb(info._d)
    return {
        "code": code,
        "bourse": info.bourse,
        "sector": info.sector,
        "price_init": info.price_init_raw,
        "last_close": info.last_close_raw,        # 现价=最后 K 线 Close（非陈旧 PriceFact）
        "rate_limit": info.rate_limit,
        "volume_total": info.volume_total_raw,
        "volume_flow": info.volume_flow_raw,
        "market_cap": int(calc_market_cap(info._d)),
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
    save = SaveModel(load_json(file))
    out = []
    for code in save.codes():
        stock = save.find(code)
        if stock:
            out.append(_stock_summary(stock.info, code))
    return {"stocks": out, "count": len(out)}


@commands.command()
async def get_stock(body: dict) -> dict:
    """取单只股票详情。body: {file, code}"""
    code = body["code"]
    stock = SaveModel(load_json(body["file"])).find(code)
    if stock is None:
        return {"error": f"X{code} 不存在"}
    return _stock_summary(stock.info, code)


@commands.command()
async def set_pe(body: dict) -> dict:
    """body: {file, code, target, save?}"""
    file, code, target = body["file"], body["code"], body["target"]
    save = body.get("save", True)
    if target == 0:
        return {"error": "PE 不能为 0"}
    data = load_json(file)
    info = SaveModel(data).find(code).info
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
    info = SaveModel(data).find(code).info
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
    info = SaveModel(data).find(code).info
    set_target_debt_ratio(info, ratio_pct)
    if save:
        write_json_compact(file, data)
    return _stock_summary(info, code)


@commands.command()
async def set_price(body: dict) -> dict:
    """body: {file, code, yuan, field?('init'|'fact'), save?}

    yuan 是显示元；core 的 set_price_init/set_price_fact_sync_candles 收显示元，
    内部 ×100 由 SaveModel setter 处理（不要再手动 ×100，否则双重）。
    """
    file, code = body["file"], body["code"]
    yuan = body["yuan"]
    field = body.get("field", "fact")
    save = body.get("save", True)
    data = load_json(file)
    info = SaveModel(data).find(code).info
    if field == "init":
        set_price_init(info, yuan)
    else:
        set_price_fact_sync_candles(info, yuan)
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
    info = SaveModel(data).find(code).info
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

    body: {file, codes:[int], pct:float(0-100), target/strategy?:str, save?}
    扣仓位策略（target 或 strategy，二者等价、strategy 优先）：
      inst/ret/hot = 按该优先顺序依次扣；
      balance_ir = 主力+散户按比例均衡；ret_then_inst = 先散户后机构(游资兜底)；
      npc_proportional = 5类NPC按比例均匀扣。缺省 'inst'。
    """
    file = body["file"]
    codes = body.get("codes")
    pct = body["pct"]
    target = body.get("target", "inst")
    strategy = body.get("strategy") or target
    sector = body.get("sector")
    save = body.get("save", True)
    data = load_json(file)
    save_model = SaveModel.from_dict(data)
    results = batch_set_player_pct(save_model, codes, pct, strategy=strategy, sector=sector)
    if save:
        write_json_compact(file, data)
    # 返回时 key 转 str（JSON 要求）
    return {"results": {str(k): v for k, v in results.items()},
            "count": len(results)}


@commands.command()
async def batch_npc_quotes(body: dict) -> dict:
    """批量设主力/散户挂单（愿意购入资金 / 卖压）。

    body: {file, codes?:[int], sector?, amount_buy?:int|null, volume_sell?:int|null,
           apply_inst?:bool, apply_ret?:bool, save?}
    """
    file = body["file"]
    data = load_json(file)
    save_model = SaveModel.from_dict(data)
    results = batch_set_npc_quotes(
        save_model, body.get("codes"),
        amount_buy=body.get("amount_buy"),
        volume_sell=body.get("volume_sell"),
        apply_inst=body.get("apply_inst", True),
        apply_ret=body.get("apply_ret", True),
        sector=body.get("sector"),
    )
    if body.get("save", True):
        write_json_compact(file, data)
    return {"results": {str(k): v for k, v in results.items()},
            "count": len(results)}


@commands.command()
async def batch_notice_style(body: dict) -> dict:
    """批量设 NPC 购买取向（NoticeStyle 个股级参数，全局生效）。

    body: {file, codes?:[int], sector?, strength?:float|null, create_prob?:float|null, save?}
    """
    file = body["file"]
    data = load_json(file)
    save_model = SaveModel.from_dict(data)
    result = batch_set_notice_style(
        save_model, body.get("codes"),
        strength=body.get("strength"),
        create_prob=body.get("create_prob"),
        sector=body.get("sector"),
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
    avg20, py, pi, ns, cost = compute_placement(candles, stock.info.last_close_raw,
                                                ratio, amount)
    if ns <= 0:
        return {"error": "新增为 0"}
    apply_private_placement(save_model, code, stock, ns, cost, candles)
    if save:
        write_json_compact(file, data)
    return {"new_shares": ns, "cost": cost, "issue_price": round(py, 2)}


# ------------------------------------------------------------------
# 单股精修（原版单股菜单补全：自由财务 / NPC挂单 / 玩家持仓）
# ------------------------------------------------------------------
@commands.command()
async def set_financials(body: dict) -> dict:
    """自由设定单股全部财务字段（防回滚，Prev=当前/Min=0）。

    body: {file, code, fields:{VolumeTotal?,VolumeFlow?,AssetNet?,AssetLoan?,
           RewardBusiness?,RewardOther?,CostBusiness?,CostOther?}}（值=内部值，按原 change_financials 语义）
    """
    file, code = body["file"], body["code"]
    fields = body.get("fields", {})
    save = body.get("save", True)
    data = load_json(file)
    save_model = SaveModel(data)
    stock = save_model.find(code)
    if stock is None:
        return {"error": f"X{code} 不存在"}
    apply_financial_fields(stock.info, fields)
    if save:
        write_json_compact(file, data)
    return _stock_summary(stock.info, code)


@commands.command()
async def set_npc_quotes(body: dict) -> dict:
    """单股主力/散户挂单：mode=median|1.5x|0.5x|clear|custom。

    body: {file, code, mode, vus?, aub?, rvus?, raub?}（custom 时给 4 个值，内部值）
    """
    file, code = body["file"], body["code"]
    mode = body.get("mode", "median")
    save = body.get("save", True)
    data = load_json(file)
    save_model = SaveModel(data)
    stock = save_model.find(code)
    if stock is None:
        return {"error": f"X{code} 不存在"}
    inst, ret = stock.institution, stock.retail
    mult = {"median": 1.0, "1.5x": 1.5, "0.5x": 0.5}.get(mode)
    if mult is not None:
        set_npc_quotes_by_median(save_model, stock, mult)
    elif mode == "clear":
        clear_npc_quotes(inst, ret)
    elif mode == "custom":
        set_npc_quotes_custom(inst, ret, body["vus"], body["aub"], body["rvus"], body["raub"])
    if save:
        write_json_compact(file, data)
    return _stock_summary(stock.info, code)


# ------------------------------------------------------------------
# 玩家持仓（原版主菜单 4：增/改/删 + 总资金）
# ------------------------------------------------------------------
@commands.command()
async def player_pos(body: dict) -> dict:
    """玩家持仓增/改/删。body: {file, mode:'add'|'modify'|'delete', code, amount?, volume?}"""
    file = body["file"]
    mode = body["mode"]
    code = body["code"]
    save = body.get("save", True)
    data = load_json(file)
    save_model = SaveModel(data)
    if mode == "add":
        add_player_position(save_model, code, body.get("amount", 0), body.get("volume", 0))
        result = {"mode": "add"}
    elif mode == "modify":
        r = modify_player_position(save_model, code, body.get("amount", 0), body.get("volume", 0))
        result = {"mode": "modify", "old_new": r}
    elif mode == "delete":
        result = {"mode": "delete", "old_raw": delete_player_position(save_model, code)}
    else:
        return {"error": f"unknown mode: {mode}"}
    if save:
        write_json_compact(file, data)
    return result


@commands.command()
async def player_amount(body: dict) -> dict:
    """改 Player.Amount（总盈亏）。body: {file, amount}（显示元）"""
    file = body["file"]
    save = body.get("save", True)
    data = load_json(file)
    SaveModel(data).player.amount = body["amount"]
    if save:
        write_json_compact(file, data)
    return {"amount_raw": SaveModel(data).player.amount_raw}


# ------------------------------------------------------------------
# 存档瘦身三件套（原版主菜单 5/6/7）
# ------------------------------------------------------------------
@commands.command()
async def clean_notice_group(body: dict) -> dict:
    """清空 Market.NoticeGroup。body: {file, save?}"""
    file = body["file"]
    save = body.get("save", True)
    data = load_json(file)
    r = clear_notice_group(SaveModel(data))
    if save:
        write_json_compact(file, data)
    return r


@commands.command()
async def clean_trade_type(body: dict) -> dict:
    """清空 Player.TradeType。body: {file, save?}"""
    file = body["file"]
    save = body.get("save", True)
    data = load_json(file)
    r = clear_trade_type(SaveModel(data))
    if save:
        write_json_compact(file, data)
    return r


@commands.command()
async def trim_huddle_npc(body: dict) -> dict:
    """裁剪每个 HuddleNpc 持仓保留前 keep 条。body: {file, keep, save?}"""
    file = body["file"]
    keep = int(body["keep"])
    save = body.get("save", True)
    data = load_json(file)
    r = trim_huddle_npc(SaveModel(data), keep)
    if save:
        write_json_compact(file, data)
    return r


# ------------------------------------------------------------------
# NPC 购买取向预设（原版主菜单 3：6 模式）
# ------------------------------------------------------------------
@commands.command()
async def set_notice_style(body: dict) -> dict:
    """设 NoticeStyle 预设模式 1-5。body: {file, mode:int(1-5), save?}"""
    file = body["file"]
    mode = int(body["mode"])
    save = body.get("save", True)
    data = load_json(file)
    save_model = SaveModel(data)
    ns = save_model.notice_style
    if not isinstance(ns, dict):
        ns = {}
        save_model._d.setdefault("Market", {})["NoticeStyle"] = ns
    ok = apply_notice_style(ns, mode)
    if save:
        write_json_compact(file, data)
    return {"applied": ok, "mode": mode, "notice_style": ns}


# ------------------------------------------------------------------
# 股票详情 / 板块列表
# ------------------------------------------------------------------
@commands.command()
async def stock_detail(body: dict) -> dict:
    """单股完整详情（公司/财务/主力/散户/最近K线）。body: {file, code}"""
    data = load_json(body["file"])
    stock = SaveModel(data).find(body["code"])
    if stock is None:
        return {"error": f"X{body['code']} 不存在"}
    info = stock.info._d
    return {
        "code": stock.info.code,
        "company": {"bourse": stock.info.bourse, "sector": stock.info.sector,
                    "volume_total": info.get("VolumeTotal", 0), "volume_flow": info.get("VolumeFlow", 0)},
        "finance": {
            "asset_net": info.get("AssetNet", 0), "asset_loan": info.get("AssetLoan", 0),
            "reward_business": info.get("RewardBusiness", 0), "reward_other": info.get("RewardOther", 0),
            "cost_business": info.get("CostBusiness", 0), "cost_other": info.get("CostOther", 0),
        },
        "institution": {"vol_sell": stock.institution.volume_usable_sell_raw,
                        "amount_buy": stock.institution.amount_usable_buy_raw},
        "retail": {"vol_sell": stock.retail.volume_usable_sell_raw,
                   "amount_buy": stock.retail.amount_usable_buy_raw},
        "candles": info.get("Candles", [])[-5:],
        "pe": (None if calc_pe(info) == float("inf") else round(calc_pe(info), 4)),
        "pb": (None if calc_pb(info) == float("inf") else round(calc_pb(info), 4)),
    }


@commands.command()
async def list_sectors(body: dict) -> dict:
    """列出存档内出现的所有 Sector + 各板块股票数。body: {file}"""
    data = load_json(body["file"])
    counts = {}
    for s in stocks_of(data):
        sec = s.get("Info", {}).get("Sector")
        if sec is not None:
            counts[sec] = counts.get(sec, 0) + 1
    return {"sectors": [{"sector": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: str(x[0]))]}


@commands.command()
async def stocks_by_sector(body: dict) -> dict:
    """列某板块下所有股票概况。body: {file, sector}"""
    data = load_json(body["file"])
    from src.core.editor import stocks_by_sector as _sbs
    out = []
    for s in _sbs(data, body["sector"]):
        out.append(_stock_summary(InfoModel(s["Info"]), s.get("Info", {}).get("Code")))
    return {"stocks": out, "count": len(out)}


# ------------------------------------------------------------------
# 公告（[extra]：发布 + 查看 + 删除）
# ------------------------------------------------------------------
@commands.command()
async def publish_notice(body: dict) -> dict:
    """[extra] 发布股票公告/业绩报告。

    body: {file, code, notice_day, star, kind:'notice'|'report',
           strength?, create_prob?, report_strength?, is_buy?,
           (report 时) asset_net, asset_loan, reward_business, reward_other, cost_business, cost_other}
    """
    file = body["file"]
    code = body["code"]
    save = body.get("save", True)
    data = load_json(file)
    save_model = SaveModel(data)
    stock = save_model.find(code)
    if stock is None:
        return {"error": f"X{code} 不存在"}
    info = stock.info
    if body.get("kind") == "report":
        rep = build_performance_report(
            code, info, body["notice_day"], body["star"], body.get("report_strength", 1.0),
            body.get("is_buy", True),
            body["asset_net"], body["asset_loan"], body["reward_business"], body["reward_other"],
            body["cost_business"], body["cost_other"])
        ok = commit_performance_report(save_model, rep)
        result = {"kind": "report", "committed": ok}
    else:
        n = build_stock_notice(code, body["notice_day"], body["star"],
                               strength=body.get("strength", 1.0), create_prob=body.get("create_prob", 0.08))
        cnt = append_notice_normal(save_model, [n])
        result = {"kind": "notice", "appended": cnt}
    if save:
        write_json_compact(file, data)
    return result


@commands.command()
async def list_notices(body: dict) -> dict:
    """[extra] 列某股的公告/业绩报告。body: {file, code}"""
    data = load_json(body["file"])
    ng = SaveModel(data).notice_group
    if not isinstance(ng, dict):
        return {"normal": [], "reports": []}
    code = body["code"]
    normal = [n for n in ng.get("NoticeNormal", []) if n.get("Code") == code]
    reports = [r for r in ng.get("NoticeReport", []) if r.get("Code") == code]
    return {"normal": normal, "reports": reports}


@commands.command()
async def delete_notice(body: dict) -> dict:
    """[extra] 删某股某类公告的指定索引。body: {file, code, kind:'normal'|'report', index}"""
    file = body["file"]
    code = body["code"]
    kind = body["kind"]
    idx = int(body["index"])
    save = body.get("save", True)
    data = load_json(file)
    save_model = SaveModel(data)
    ng = save_model.notice_group
    key = "NoticeNormal" if kind == "normal" else "NoticeReport"
    lst = ng.get(key, []) if isinstance(ng, dict) else []
    target = [i for i, n in enumerate(lst) if n.get("Code") == code]
    if idx < 0 or idx >= len(target):
        return {"error": "索引超出范围"}
    del lst[target[idx]]
    if save:
        write_json_compact(file, data)
    return {"deleted": True, "remaining": sum(1 for n in lst if n.get("Code") == code)}
