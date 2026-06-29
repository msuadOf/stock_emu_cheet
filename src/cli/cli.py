"""非交互式命令行（子命令式）：直接调用 ``src.core`` 纯后端做存档编辑。

设计：每个子命令打开一份存档 → 执行一个 core 操作 → 可选保存 → 退出。
完全可脚本化/批处理。**只 import ``src.core``**，绝不 import tui（避免把交互栈
与 subprocess 副作用拉进 CLI，且杜绝环导入）。

用法示例::

    python -m src.cli.cli list-saves -d <存档目录>
    python -m src.cli.cli set-pe 2001 1.0 --save <文件.sav> --yes
    python -m src.cli.cli save --save <文件.sav> --force
"""
import argparse
import sys
from pathlib import Path

# 只依赖共享业务后端
from src.core import (
    DEFAULT_SAVE_DIR,
    SECTOR_MAP,
    default_save_dir,
    list_save_slots,
    list_save_files,
    load_json,
    write_json_compact,
    stocks_of,
    find_stock,
    codes_of,
    codes_by_sector,
    calc_pe, calc_pb, calc_market_cap,
    fmt_p, fmt_m, fmt_shares, last_close_raw,
    set_target_pe, set_target_pb, set_target_debt_ratio,
    set_price_init, set_price_fact_sync_candles, set_rate_limit,
    apply_financial_fields, apply_notice_style,
    set_npc_quotes_by_median, set_npc_quotes_custom, clear_npc_quotes,
    add_player_position, modify_player_position, delete_player_position, set_player_amount,
    clear_notice_group, clear_trade_type, trim_huddle_npc,
    parse_magnitude,
)
# extra 子命令（分组：Extra 功能）
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


# ------------------------------------------------------------------
# 存档打开/保存助手（复用 core 的纯函数；不引入 TUI 的 Editor 类）
# ------------------------------------------------------------------
def _open(save_path):
    return load_json(save_path)


def _resolve_code(data, code):
    code = int(code)
    if find_stock(data, code) is None:
        raise SystemExit(f"错误：股票 X{code} 不存在于存档")
    return code


def _commit(args, data, modified=True, force=False):
    """若 args.save 给定且（args.yes 或 force），则写回磁盘（无备份/无交互）。"""
    if args.save and modified:
        if args.yes or force:
            write_json_compact(args.save, data)
            print(f"已保存：{args.save}")
        else:
            print("（未加 --yes，改动未写盘）")


# ------------------------------------------------------------------
# 子命令实现
# ------------------------------------------------------------------
def cmd_list_saves(args):
    """列出默认(或 -d 指定)存档目录下的槽与 .sav 文件，供用户选择。"""
    base = args.save_dir
    print(f"存档目录: {base}")
    slots = list_save_slots(base)
    if not slots:
        print("  （无存档槽 / 目录不存在）")
        return
    for slot in slots:
        print(f"\n[{slot['name']}]  ({slot['file_count']} 个 .sav)")
        for f in list_save_files(slot["path"]):
            print(f"  {f['size_kb']:>9.1f} KB   {f['modified']}   {f['path']}")


def cmd_show(args):
    data = _open(args.save)
    code = _resolve_code(data, args.code)
    stock = find_stock(data, code)
    info = stock["Info"]
    print(f"=== X{code} ===")
    print(f"  PriceInit 发行价: {fmt_p(info['PriceInit'])}")
    print(f"  昨收/最新价: {fmt_p(last_close_raw(info))}  (PriceFact={fmt_p(info['PriceFact'])}, 陈旧参考值)")
    print(f"  RateLimit 涨跌幅: {round(info['RateLimit']*100,1)}%")
    print(f"  总股本: {fmt_shares(info.get('VolumeTotal',0))}")
    print(f"  流通股: {fmt_shares(info.get('VolumeFlow',0))}")
    print(f"  市值:   {fmt_m(int(calc_market_cap(info)))}")
    pe = calc_pe(info); pb = calc_pb(info)
    print(f"  PE: {'N/A' if pe==float('inf') else round(pe,4)}")
    print(f"  PB: {'N/A' if pb==float('inf') else round(pb,4)}")


def cmd_set_pe(args):
    data = _open(args.save)
    code = _resolve_code(data, args.code)
    if args.target == 0:
        raise SystemExit("错误：PE 不能为 0")
    set_target_pe(find_stock(data, code)["Info"], args.target)
    _commit(args, data)
    pe = calc_pe(find_stock(data, code)["Info"])
    print(f"X{code} 新 PE = {round(pe,4)}")


def cmd_set_pb(args):
    data = _open(args.save)
    code = _resolve_code(data, args.code)
    set_target_pb(find_stock(data, code)["Info"], args.target)
    _commit(args, data)
    pb = calc_pb(find_stock(data, code)["Info"])
    print(f"X{code} 新 PB = {round(pb,4)}")


def cmd_set_debt(args):
    data = _open(args.save)
    code = _resolve_code(data, args.code)
    set_target_debt_ratio(find_stock(data, code)["Info"], args.ratio)
    _commit(args, data)
    print(f"X{code} 负债率已设为 {args.ratio}%")


def cmd_set_price(args):
    data = _open(args.save)
    code = _resolve_code(data, args.code)
    info = SaveModel.from_dict(data).find(code).info   # InfoModel（core 已迁移）
    if args.field == "init":
        set_price_init(info, args.yuan)                 # 显示元，内部 ×100 由 setter 处理
    else:
        set_price_fact_sync_candles(info, args.yuan)
    _commit(args, data)
    raw = info.price_init_raw if args.field == "init" else info.last_close_raw
    label = "发行价" if args.field == "init" else "昨收/最新价"
    print(f"X{code} {label} 已设为 {fmt_p(raw)}（内部 {raw}）")


def cmd_set_ratelimit(args):
    data = _open(args.save)
    code = _resolve_code(data, args.code)
    set_rate_limit(find_stock(data, code)["Info"], args.pct)
    _commit(args, data)
    print(f"X{code} RateLimit 已设为 {args.pct}%")


def cmd_save(args):
    data = _open(args.save)
    # CLI 永远强制保存（无交互 confirm）；--force 只是显式开关
    write_json_compact(args.save, data)
    print(f"已保存：{args.save}")


# ---- extra 子命令 ----
def cmd_rectify(args):
    data = _open(args.save)
    save = SaveModel.from_dict(data)
    summary = rectify_market(save)
    for c, r in summary.items():
        print(f"  X{c}: {r}")
    _commit(args, data, force=True)
    print("市场整顿完成")


def cmd_npc_to_retail(args):
    data = _open(args.save)
    save = SaveModel.from_dict(data)
    moved = move_npc_to_retail(save)
    for c, v in moved.items():
        print(f"  X{c}: +{v} -> Retail")
    _commit(args, data, force=True)
    print(f"砍机构转散户完成，{len(moved)} 只股票")


def cmd_delist(args):
    data = _open(args.save)
    save = SaveModel.from_dict(data)
    for code in args.codes:
        code = int(code)
        if args.to_b:
            stock, positions = delist_to_b(save, code)
            print(f"  X{code} 已退市进 B 集合（清玩家持仓 {len(positions)} 条）")
        else:
            if delist_to_a(save, code):
                print(f"  X{code} 已进 A 集合（RateLimit=5%）")
    _commit(args, data, force=True)


def cmd_dividend(args):
    data = _open(args.save)
    code = _resolve_code(data, args.code)
    save = SaveModel.from_dict(data)
    stock = save.find(code)
    if args.stock_gift is not None:
        apply_stock_dividend(save, code, stock, args.stock_gift)
        print(f"X{code} 10送{args.stock_gift} 完成")
    if args.cash is not None:
        vols = collect_dividend_vols(save, code, stock)
        D_int = int(args.cash * 100)
        max_total, max_D = cash_dividend_limits(stock.info, sum(vols.values()))
        if D_int > max_D:
            raise SystemExit(f"错误：每手分红 {args.cash} 超过上限 {round(max_D/100,2)}")
        total = apply_cash_dividend(save, code, stock, vols, D_int)
        print(f"X{code} 现金分红完成，总派现 {fmt_m(total)}")
    _commit(args, data, force=True)


def cmd_placement(args):
    data = _open(args.save)
    code = _resolve_code(data, args.code)
    save = SaveModel.from_dict(data)
    stock = save.find(code)
    candles = stock.info._d.get("Candles", []) or []
    avg20, py, pi, ns, cost = compute_placement(candles, stock.info.price_fact_raw,
                                                args.ratio, args.amount)
    if ns <= 0:
        print("新增为 0，跳过"); return
    apply_private_placement(save, code, stock, ns, cost, candles)
    print(f"X{code} 定向增发完成：新增 {ns} 股(内部)，玩家支付 {fmt_m(cost)}")
    _commit(args, data, force=True)


# ------------------------------------------------------------------
# 单股精修（补全原版单股菜单）
# ------------------------------------------------------------------
def cmd_set_financials(args):
    data = _open(args.save)
    code = _resolve_code(data, args.code)
    save = SaveModel.from_dict(data)
    fields = {k: v for k, v in {
        "VolumeTotal": args.vol_total, "VolumeFlow": args.vol_flow,
        "AssetNet": args.asset_net, "AssetLoan": args.asset_loan,
        "RewardBusiness": args.reward_b, "RewardOther": args.reward_o,
        "CostBusiness": args.cost_b, "CostOther": args.cost_o,
    }.items() if v is not None}
    if not fields:
        raise SystemExit("错误：至少给一个财务字段")
    apply_financial_fields(save.find(code).info, fields)
    print(f"X{code} 已设 {len(fields)} 个财务字段（Prev 同步、Min 归零）")
    _commit(args, data, force=True)


def cmd_set_npc_quotes(args):
    data = _open(args.save)
    code = _resolve_code(data, args.code)
    save = SaveModel.from_dict(data)
    stock = save.find(code)
    inst, ret = stock.institution, stock.retail
    mult = {"median": 1.0, "1.5x": 1.5, "0.5x": 0.5}.get(args.mode)
    if mult is not None:
        set_npc_quotes_by_median(save, stock, mult)
        print(f"X{code} 挂单设为 {args.mode} 中位数")
    elif args.mode == "clear":
        clear_npc_quotes(inst, ret)
        print(f"X{code} 挂单清零")
    elif args.mode == "custom":
        set_npc_quotes_custom(inst, ret, args.vus, args.aub, args.rvus, args.raub)
        print(f"X{code} 挂单自定义：主力卖{args.vus}/买{args.aub}，散户卖{args.rvus}/买{args.raub}")
    _commit(args, data, force=True)


def cmd_player_pos(args):
    data = _open(args.save)
    code = int(args.code)
    save = SaveModel.from_dict(data)
    if args.mode == "add":
        add_player_position(save, code, args.amount or 0, args.volume or 0)
        print(f"已添加玩家持仓 X{code}：盈亏 {args.amount or 0}，股数 {args.volume or 0}")
    elif args.mode == "modify":
        r = modify_player_position(save, code, args.amount or 0, args.volume or 0)
        print(f"已修改 X{code} 持仓：{r}")
    elif args.mode == "delete":
        old = delete_player_position(save, code)
        print(f"已删除 X{code} 持仓（原 VolumeUsable={old}）" if old is not None else f"X{code} 无持仓")
    _commit(args, data, force=True)


def cmd_player_amount(args):
    data = _open(args.save)
    SaveModel.from_dict(data).player.amount = args.amount
    print(f"玩家总资金设为 {args.amount}（显示元）")
    _commit(args, data, force=True)


# ------------------------------------------------------------------
# 存档瘦身三件套 + NPC取向预设
# ------------------------------------------------------------------
def cmd_clean_notice_group(args):
    data = _open(args.save)
    r = clear_notice_group(SaveModel.from_dict(data))
    print(f"已清空 NoticeGroup（{r['form']}，清掉 {r['before']} 条）")
    _commit(args, data, force=True)


def cmd_clean_trade_type(args):
    data = _open(args.save)
    r = clear_trade_type(SaveModel.from_dict(data))
    print(f"已清空 TradeType（{r['before']} 条）")
    _commit(args, data, force=True)


def cmd_trim_hn(args):
    data = _open(args.save)
    r = trim_huddle_npc(SaveModel.from_dict(data), args.keep)
    print(f"HuddleNpc 裁剪：{r['before']} -> {r['after']} 条（{r['accounts']} 个账户）")
    _commit(args, data, force=True)


def cmd_notice_style(args):
    data = _open(args.save)
    save = SaveModel.from_dict(data)
    ns = save.notice_style
    if not isinstance(ns, dict):
        ns = {}
        save._d.setdefault("Market", {})["NoticeStyle"] = ns
    ok = apply_notice_style(ns, args.mode)
    print(f"NoticeStyle 模式 {args.mode}：{'已应用' if ok else '未知模式(1-5)'}")
    _commit(args, data, force=True)


# ------------------------------------------------------------------
# 详情 / 板块
# ------------------------------------------------------------------
def cmd_show_detail(args):
    data = _open(args.save)
    code = _resolve_code(data, args.code)
    info = SaveModel.from_dict(data).find(code).info._d
    print(f"=== X{code} 完整详情 ===")
    print(f"  交易所/板块: {info.get('Bourse')} / {info.get('Sector')}")
    print(f"  价格: 昨收/最新={fmt_p(last_close_raw(info))}  PriceInit={fmt_p(info.get('PriceInit', 0))}  PriceFact={fmt_p(info.get('PriceFact', 0))}(陈旧)  RateLimit={round(info.get('RateLimit',0)*100,1)}%")
    print(f"  股本: 总{fmt_shares(info.get('VolumeTotal',0))}  流通{fmt_shares(info.get('VolumeFlow',0))}")
    print(f"  财务: 净资产{fmt_m(info.get('AssetNet',0))} 负债{fmt_m(info.get('AssetLoan',0))} "
          f"收益{fmt_m(info.get('RewardBusiness',0)+info.get('RewardOther',0))} "
          f"成本{fmt_m(info.get('CostBusiness',0)+info.get('CostOther',0))}")
    print(f"  PE={round(calc_pe(info),4) if calc_pe(info)!=float('inf') else 'N/A'}  "
          f"PB={round(calc_pb(info),4) if calc_pb(info)!=float('inf') else 'N/A'}")
    candles = info.get("Candles", [])[-5:]
    if candles:
        print(f"  最近 {len(candles)} 根 K 线：")
        for c in candles:
            print(f"    Day{c.get('Day')} C={fmt_p(c.get('Close',0))} V={c.get('Volume',0)}")


def cmd_list_by_sector(args):
    data = _open(args.save)
    codes = codes_by_sector(data, args.sector)
    print(f"板块 {args.sector} 下 {len(codes)} 只股票：")
    for c in codes:
        s = find_stock(data, c)
        if s:
            print(f"  X{c}  昨收 {fmt_p(last_close_raw(s['Info']))}")


# ------------------------------------------------------------------
# 公告（[extra]）
# ------------------------------------------------------------------
def cmd_publish_notice(args):
    data = _open(args.save)
    code = _resolve_code(data, args.code)
    save = SaveModel.from_dict(data)
    stock = save.find(code)
    if args.kind == "report":
        rep = build_performance_report(
            code, stock.info, args.day, args.star, args.report_strength or 1.0, args.is_buy,
            args.asset_net or 0, args.asset_loan or 0, args.reward_b or 0, args.reward_o or 0,
            args.cost_b or 0, args.cost_o or 0)
        ok = commit_performance_report(save, rep)
        print(f"X{code} 业绩报告 {'已提交' if ok else '失败'}")
    else:
        n = build_stock_notice(code, args.day, args.star, strength=args.strength or 1.0)
        cnt = append_notice_normal(save, [n])
        print(f"X{code} 公告已发布 {cnt} 条")
    _commit(args, data, force=True)


def cmd_list_notices(args):
    data = _open(args.save)
    code = int(args.code)
    ng = SaveModel.from_dict(data).notice_group
    if not isinstance(ng, dict):
        print("无公告"); return
    normal = [n for n in ng.get("NoticeNormal", []) if n.get("Code") == code]
    reports = [r for r in ng.get("NoticeReport", []) if r.get("Code") == code]
    print(f"X{code} 公告 {len(normal)} 条 / 业绩报告 {len(reports)} 条")
    for i, n in enumerate(normal):
        print(f"  [公告{i}] Star={n.get('Star')} Prob={round(n.get('Prob',0),4)} Day={n.get('Day')}")
    for i, r in enumerate(reports):
        print(f"  [报告{i}] Star={r.get('Star')} Prob={round(r.get('Prob',0),4)} Day={r.get('Day')}")


# ------------------------------------------------------------------
# 参数解析
# ------------------------------------------------------------------
def build_parser():
    p = argparse.ArgumentParser(
        prog="sse-cli",
        description="StocksMainForceSimulator 存档编辑器（非交互式 CLI）",
    )
    p.add_argument("-d", "--save-dir", dest="save_dir", type=Path,
                   default=DEFAULT_SAVE_DIR, help="存档根目录（list-saves 用）")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("list-saves", help="列出存档目录下的 .sav")
    sp.set_defaults(func=cmd_list_saves)

    def add_save(sp):
        sp.add_argument("--save", type=Path, required=True, help="要操作的 .sav 文件路径")
        sp.add_argument("--yes", action="store_true", help="写回磁盘（否则只预览）")

    def add_code(sp):
        sp.add_argument("code", help="股票代码（如 2001）")

    sp = sub.add_parser("show", help="查看某只股票概况")
    add_code(sp); add_save(sp); sp.set_defaults(func=cmd_show)

    sp = sub.add_parser("set-pe", help="设定目标 PE（反推净利润）")
    add_code(sp); sp.add_argument("target", type=float); add_save(sp); sp.set_defaults(func=cmd_set_pe)

    sp = sub.add_parser("set-pb", help="设定目标 PB（反推净资产）")
    add_code(sp); sp.add_argument("target", type=float); add_save(sp); sp.set_defaults(func=cmd_set_pb)

    sp = sub.add_parser("set-debt", help="设定目标负债率(百分数)")
    add_code(sp); sp.add_argument("ratio", type=float); add_save(sp); sp.set_defaults(func=cmd_set_debt)

    sp = sub.add_parser("set-price", help="设定价格（init=发行价 / fact=昨收，单位元）")
    add_code(sp); sp.add_argument("yuan", type=float); sp.add_argument("--field", choices=["init", "fact"], default="fact")
    add_save(sp); sp.set_defaults(func=cmd_set_price)

    sp = sub.add_parser("set-ratelimit", help="设定涨跌停幅度(百分数)")
    add_code(sp); sp.add_argument("pct", type=float); add_save(sp); sp.set_defaults(func=cmd_set_ratelimit)

    sp = sub.add_parser("save", help="把存档写回磁盘（CLI 总是强制，无交互确认）")
    add_save(sp); sp.set_defaults(func=cmd_save)

    # ===== Extra 功能（分组）=====
    g_extra = sp  # 复用变量名占位；下面每个 extra 子命令的 help 文案都标注 [Extra]

    sp = sub.add_parser("rectify", help="[Extra] 市场整顿：强制筹码守恒")
    add_save(sp); sp.set_defaults(func=cmd_rectify)

    sp = sub.add_parser("npc-to-retail", help="[Extra] 砍机构持仓转散户")
    add_save(sp); sp.set_defaults(func=cmd_npc_to_retail)

    sp = sub.add_parser("delist", help="[Extra] 退市（默认进A集合警告；--to-b 完全退市）")
    add_save(sp); sp.add_argument("codes", nargs="+"); sp.add_argument("--to-b", action="store_true")
    sp.set_defaults(func=cmd_delist)

    sp = sub.add_parser("dividend", help="[Extra] 分红（--cash 每手元 / --stock 10送X）")
    add_code(sp); add_save(sp)
    sp.add_argument("--cash", type=float); sp.add_argument("--stock", dest="stock_gift", type=int)
    sp.set_defaults(func=cmd_dividend)

    sp = sub.add_parser("placement", help="[Extra] 定向增发（--ratio 折价率 --amount 玩家支付元）")
    add_code(sp); add_save(sp)
    sp.add_argument("--ratio", type=float, default=0.8); sp.add_argument("--amount", type=float, default=1_000_000)
    sp.set_defaults(func=cmd_placement)

    # ===== 单股精修 =====
    sp = sub.add_parser("set-financials", help="自由设定财务字段（防回滚）")
    add_code(sp); add_save(sp)
    for n, h in [("vol_total","VolumeTotal"),("vol_flow","VolumeFlow"),("asset_net","AssetNet"),
                 ("asset_loan","AssetLoan"),("reward_b","RewardBusiness"),("reward_o","RewardOther"),
                 ("cost_b","CostBusiness"),("cost_o","CostOther")]:
        sp.add_argument(f"--{n}", type=int, help=f"{h}（内部值，可选）")
    sp.set_defaults(func=cmd_set_financials)

    sp = sub.add_parser("set-npc-quotes", help="主力/散户挂单（median/1.5x/0.5x/clear/custom）")
    add_code(sp); add_save(sp)
    sp.add_argument("mode", choices=["median", "1.5x", "0.5x", "clear", "custom"])
    sp.add_argument("--vus", type=int, default=0, help="主力可卖(custom)")
    sp.add_argument("--aub", type=int, default=0, help="主力资金(custom)")
    sp.add_argument("--rvus", type=int, default=0, help="散户可卖(custom)")
    sp.add_argument("--raub", type=int, default=0, help="散户资金(custom)")
    sp.set_defaults(func=cmd_set_npc_quotes)

    sp = sub.add_parser("player-pos", help="玩家持仓 增/改/删")
    add_save(sp)
    sp.add_argument("mode", choices=["add", "modify", "delete"])
    sp.add_argument("code"); sp.add_argument("--amount", type=int); sp.add_argument("--volume", type=int)
    sp.set_defaults(func=cmd_player_pos)

    sp = sub.add_parser("player-amount", help="改玩家总资金（显示元）")
    add_save(sp); sp.add_argument("amount", type=int)
    sp.set_defaults(func=cmd_player_amount)

    # ===== 存档瘦身 + NPC取向 =====
    sp = sub.add_parser("clean-ng", help="清空公告历史 NoticeGroup")
    add_save(sp); sp.set_defaults(func=cmd_clean_notice_group)

    sp = sub.add_parser("clean-tt", help="清空交易历史 Player.TradeType")
    add_save(sp); sp.set_defaults(func=cmd_clean_trade_type)

    sp = sub.add_parser("trim-hn", help="裁剪 HuddleNpc 持仓（保留前N条）")
    add_save(sp); sp.add_argument("keep", type=int, help="每个NPC保留几条")
    sp.set_defaults(func=cmd_trim_hn)

    sp = sub.add_parser("notice-style", help="NPC购买取向预设（模式1-5）")
    add_save(sp); sp.add_argument("mode", type=int, choices=[1, 2, 3, 4, 5])
    sp.set_defaults(func=cmd_notice_style)

    # ===== 详情 / 板块 =====
    sp = sub.add_parser("show-detail", help="查看股票完整详情")
    add_code(sp); add_save(sp); sp.set_defaults(func=cmd_show_detail)

    sp = sub.add_parser("list-by-sector", help="列某板块下所有股票")
    add_save(sp); sp.add_argument("sector", help="Sector 板块号")
    sp.set_defaults(func=cmd_list_by_sector)

    # ===== 公告（Extra）=====
    sp = sub.add_parser("publish-notice", help="[Extra] 发布公告/业绩报告")
    add_code(sp); add_save(sp)
    sp.add_argument("--kind", choices=["notice", "report"], default="notice")
    sp.add_argument("--day", type=int, default=1); sp.add_argument("--star", type=int, default=3)
    sp.add_argument("--strength", type=float); sp.add_argument("--report-strength", type=float)
    sp.add_argument("--is-buy", action="store_true")
    for n in ["asset_net", "asset_loan", "reward_b", "reward_o", "cost_b", "cost_o"]:
        sp.add_argument(f"--{n}", type=int)
    sp.set_defaults(func=cmd_publish_notice)

    sp = sub.add_parser("list-notices", help="[Extra] 查看某股公告/业绩报告")
    add_code(sp); add_save(sp); sp.set_defaults(func=cmd_list_notices)

    return p


def cli_main(argv=None):
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(cli_main())
