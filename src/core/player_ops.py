"""玩家持仓(Player.StockPos) 编辑的纯核心（原主干功能，已迁移到 SaveModel）。

把原 TUI ``change_player`` 中「改持仓 + 筹码守恒同步 + 智能增发」的纯部分剥离。
交互（prompt/print/confirm/选过户对象）仍留 TUI。函数收 SaveModel/StockModel/
AccountModel/PositionModel，全程显示单位（getter/setter），×100 由 model 处理。
"""
from .stock_ops import dilute_for_shortage


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


def batch_set_player_pct(save, codes, pct, target_account="inst"):
    """批量把玩家对一组股票的持仓设为各自流通股(VolumeFlow)的 pct%。

    save: SaveModel。pct: 显示百分数 0~100（如 10 = 持仓流通股的 10%）。
    target_account: 优先扣减账户 'inst'/'ret'，不够再扣另一个。
    全程**显示单位**（流通股×pct% 无歧义），×100 由 model setter 处理。

    筹码守恒：玩家持仓变化从「散户+主力」可卖里**同步削减/回补**，不增发。
    数据模型提示：市场可卖筹码通常只占流通股 ~0.87%，pct 超过可卖比例时
    无法足额划转—— shortfall 如实记录，玩家仍获目标持仓，绝不凭空增发。

    返回 {code: {volume(显示股), volume_raw, taken_from, action, shortfall_shares,
                 sellable_ratio_pct}}。
    """
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

        inst, ret = stock.institution, stock.retail
        order = ([(inst, "inst"), (ret, "ret")] if target_account == "inst"
                 else [(ret, "ret"), (inst, "inst")])
        taken_from = {"inst": 0, "ret": 0}
        action, shortfall = "noop", 0
        if delta != 0 and target_account:
            if delta > 0:                        # 玩家加仓：从 order 各账户可卖里扣
                need = delta
                for acc, key in order:
                    if need <= 0:
                        break
                    if acc.is_unlimited:
                        continue
                    cur = acc.volume_usable_sell
                    take = min(cur, need)
                    acc.volume_usable_sell = cur - take
                    taken_from[key] = take
                    need -= take
                action = "shortage" if need > 0 else "transferred"
                shortfall = need
            else:                                # 玩家减仓：还给优先账户
                give = -delta
                if order[0][0].is_unlimited:
                    action = "returned"
                else:
                    cur = order[0][0].volume_usable_sell
                    order[0][0].volume_usable_sell = cur + give
                    taken_from[order[0][1]] = -give
                    action = "returned"
        sellable_ratio = (round(stock.sellable_chips / flow * 100, 4) if flow else 0)
        results[code] = {
            "volume": target_shares,                     # 显示股（修复点）
            "volume_raw": int(round(target_shares * 100)),
            "taken_from": taken_from,
            "action": action,
            "shortfall_shares": shortfall,
            "sellable_ratio_pct": sellable_ratio,
        }
    return results

