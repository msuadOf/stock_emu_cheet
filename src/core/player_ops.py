"""玩家持仓(Player.StockPos) 编辑的纯核心（原主干功能，已迁移到 SaveModel）。

把原 TUI ``change_player`` 中「改持仓 + 筹码守恒同步 + 智能增发」的纯部分剥离。
交互（prompt/print/confirm/选过户对象）仍留 TUI。函数收 SaveModel/StockModel/
AccountModel/PositionModel，全程显示单位（getter/setter），×100 由 model 处理。
"""
from .stock_ops import dilute_for_shortage
from .savemodel import NPC_KEYS


def add_player_position(save, code, amount, volume):
    """添加一条玩家持仓。save: SaveModel。amount/volume: 显示元/显示股。"""
    save.player.upsert_position(code)  # 确保存在
    pos = save.player.find_position(code)
    pos.amount = amount
    pos.volume_usable = volume


def modify_player_position(save, code, amount, volume):
    """修改指定 code 的玩家持仓。返回 (old_vol显示股, new_vol显示股)，未找到返回 None。"""
    pos = save.player.find_position(code)
    if pos is None:
        return None
    old_vol = pos.volume_usable
    pos.amount = amount
    pos.volume_usable = volume
    return old_vol, volume


def delete_player_position(save, code):
    """删除指定 code 的玩家持仓；返回删除前的 VolumeUsable_raw（未找到返回 None）。"""
    return save.player.remove_position(code)


def set_player_amount(save, amount):
    """修改玩家总资金 Player.Amount。amount: 显示元。"""
    save.player.amount = amount


def sync_npc_holdings(stock, delta, target, hot=None):
    """玩家持仓变化 delta(=new-old) 后，同步 NPC 持仓（筹码守恒 + 智能增发）。

    stock: StockModel；target: AccountModel（inst/ret/hot 之一）或 None。
    delta: **显示股**（>0 玩家加仓 NPC 减少；<0 玩家减仓 NPC 增加）。
    返回 (action, info)：
        ("unlimited", None)         NPC 无限制(-1)，无需变动
        ("diluted", shortage显示股) 触发增发
        ("reduced", new_npc_vol显示股) NPC 普通扣减
        ("increased", new_npc_vol显示股) NPC 普通增加
        ("noop", None)              target 为空或 delta==0
    """
    if target is None or delta == 0:
        return ("noop", None)
    if target.is_unlimited:
        return ("unlimited", None)
    cur = target.volume_usable_sell        # 显示股
    if delta > 0:  # 玩家买入，NPC 减少
        shortage = delta - cur
        if shortage > 0:
            dilute_for_shortage(stock, shortage)   # shortage 显示股
            target.volume_usable_sell = 0
            return ("diluted", shortage)
        target.volume_usable_sell = cur - delta
        return ("reduced", target.volume_usable_sell)
    else:  # 玩家卖出(delta<0)，NPC 增加
        target.volume_usable_sell = cur + abs(delta)
        return ("increased", target.volume_usable_sell)


def batch_set_player_pct(save, codes, pct, target_account="inst", strategy=None):
    """批量把玩家对一组股票的持仓设为各自流通股(VolumeFlow)的 pct%。

    save: SaveModel。pct: 显示百分数 0~100（如 10 = 持仓流通股的 10%）。

    扣仓位策略（strategy，向后兼容 target_account）：
      - "inst" / "ret" / "hot"：按该优先顺序依次扣（不够扣下一个）。hot 兜底到 inst/ret。
      - "balance_ir"：主力+散户按各自可卖筹码**比例均衡**分摊扣减。
      - "ret_then_inst"：先散户、后机构，最后游资兜底。
      - "npc_proportional"：5 类 NPC 按各自可卖筹码**比例均匀**扣（不碰主力/散户/游资）。
    target_account（旧参数）等价于 strategy（'inst'/'ret'/'hot'），传 strategy 时优先。

    全程**显示单位**（流通股×pct% 无歧义），×100 由 model setter 处理。
    筹码守恒：玩家加仓从对应账户可卖里削减、减仓回补，不增发。pct 超过可卖比例时
    shortfall 如实记录，玩家仍获目标持仓，绝不凭空增发。

    返回 {code: {volume(显示股), volume_raw, taken_from, action, shortfall_shares,
                 sellable_ratio_pct}}。
    """
    strat = strategy or target_account or "inst"
    fraction = pct / 100.0
    results = {}
    for code in codes:
        stock = save.find(code)
        if stock is None:
            continue
        info = stock.info
        flow = info.volume_flow                  # 显示股
        target_shares = int(round(flow * fraction))
        pos = save.player.upsert_position(code)
        old_shares = int(round(pos.volume_usable))
        delta = target_shares - old_shares       # 显示股
        pos.volume_usable = target_shares

        # 组装该策略下的「账户 + 标签」候选列表（顺序型策略）或按比例集合
        accounts = _resolve_accounts(stock, strat)   # [(AccountModel, label), ...]
        taken_from = {label: 0 for _, label in accounts}
        # 兜底：确保 inst/ret 键存在（前端展示用）
        taken_from.setdefault("inst", 0)
        taken_from.setdefault("ret", 0)
        action, shortfall = "noop", 0
        if delta != 0:
            if delta > 0:                        # 玩家加仓：从候选账户扣
                if strat in ("balance_ir", "npc_proportional"):
                    need = _take_proportional(accounts, delta, taken_from)
                else:
                    need = _take_ordered(accounts, delta, taken_from)
                action = "shortage" if need > 0 else "transferred"
                shortfall = need
            else:                                # 玩家减仓：还给候选第一个非无限制账户
                give = -delta
                _give_back(accounts, give, taken_from)
                action = "returned"
        sellable_ratio = (round(stock.sellable_chips / flow * 100, 4) if flow else 0)
        results[code] = {
            "volume": target_shares,                     # 显示股
            "volume_raw": int(round(target_shares * 100)),
            "taken_from": taken_from,
            "action": action,
            "shortfall_shares": shortfall,
            "sellable_ratio_pct": sellable_ratio,
        }
    return results


# 策略 → 候选账户顺序（顺序型策略）
# 顺序型：inst=[inst,ret]，ret=[ret,inst]，hot=[hot,inst,ret]，ret_then_inst=[ret,inst,hot]
# 按比例型（balance_ir / npc_proportional）单独处理，这里也返回账户集
def _resolve_accounts(stock, strat):
    """返回 [(AccountModel, label), ...] 候选账户列表（按策略）。跳过 None。"""
    inst, ret = stock.institution, stock.retail
    hot = stock.hot_money
    if strat == "inst":
        accs = [(inst, "inst"), (ret, "ret")]
    elif strat == "ret":
        accs = [(ret, "ret"), (inst, "inst")]
    elif strat == "hot":
        accs = ([(hot, "hot")] if hot is not None else []) + [(inst, "inst"), (ret, "ret")]
    elif strat == "ret_then_inst":
        accs = [(ret, "ret"), (inst, "inst")] + ([(hot, "hot")] if hot is not None else [])
    elif strat == "balance_ir":
        accs = [(inst, "inst"), (ret, "ret")]
    elif strat == "npc_proportional":
        accs = []
        for kind in NPC_KEYS:
            for i, acc in enumerate(stock.npc_accounts(kind)):
                accs.append((acc, kind if i == 0 else f"{kind}#{i}"))
    else:
        accs = [(inst, "inst"), (ret, "ret")]
    return [(a, lbl) for a, lbl in accs if a is not None]


def _take_ordered(accounts, need, taken_from):
    """顺序扣：按 accounts 顺序从各账户可卖里扣，返回未满足的 need。"""
    for acc, label in accounts:
        if need <= 0:
            break
        if acc.is_unlimited:
            continue
        cur = acc.volume_usable_sell
        take = min(cur, need)
        acc.volume_usable_sell = cur - take
        taken_from[label] = taken_from.get(label, 0) + take
        need -= take
    return need


def _take_proportional(accounts, need, taken_from):
    """按比例扣：按各账户可卖筹码占总额的比例分摊 need，返回未满足的 need。"""
    # 可卖总额（排除无限制账户；无限制直接全扣它一个即可）
    unlimited = [a for a, _ in accounts if a.is_unlimited]
    if unlimited:
        acc, label = unlimited[0], accounts[0][1] if accounts[0][0].is_unlimited else \
            next(l for a, l in accounts if a.is_unlimited)
        take = need
        taken_from[label] = taken_from.get(label, 0) + take
        return 0
    finite = [(a, label, a.volume_usable_sell) for a, label in accounts
              if not a.is_unlimited]
    total = sum(cur for _, _, cur in finite)
    if total <= 0:
        return need
    remaining = need
    # 按比例分摊（最后一个吃掉取整误差，保证不超扣、尽量扣满）
    for idx, (acc, label, cur) in enumerate(finite):
        if remaining <= 0:
            break
        if idx == len(finite) - 1:
            take = min(cur, remaining)            # 末位兜底取整误差
        else:
            take = min(cur, round(need * cur / total))
        acc.volume_usable_sell = cur - take
        taken_from[label] = taken_from.get(label, 0) + take
        remaining -= take
    return remaining


def _give_back(accounts, give, taken_from):
    """玩家减仓：把 give 股还给候选第一个非无限制账户。"""
    for acc, label in accounts:
        if not acc.is_unlimited:
            cur = acc.volume_usable_sell
            acc.volume_usable_sell = cur + give
            taken_from[label] = taken_from.get(label, 0) - give
            return
    # 全是无限制 → 不动（无需回补）


