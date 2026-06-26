"""玩家持仓(Player.StockPos) 编辑的纯核心（原主干功能）。

把原 TUI ``change_player`` 中「改持仓 + 筹码守恒同步 + 智能增发」的纯部分剥离。
交互（prompt/print/confirm/选过户对象）仍留 TUI。
"""
from .stock_ops import dilute_for_shortage


def add_player_position(e, code, amount, volume):
    """添加一条玩家持仓。"""
    e.data["Player"]["StockPos"].append({"Code": code, "Amount": amount, "VolumeUsable": volume})


def modify_player_position(e, code, amount, volume):
    """修改指定 code 的玩家持仓(Amount/VolumeUsable)。返回 (old_vol, new_vol)，
    未找到返回 None。"""
    for p in e.data["Player"]["StockPos"]:
        if p.get("Code") == code:
            old_vol = p.get("VolumeUsable", 0)
            p["Amount"] = amount
            p["VolumeUsable"] = volume
            return old_vol, volume
    return None


def delete_player_position(e, code):
    """删除指定 code 的玩家持仓；返回删除前的 VolumeUsable（未找到返回 None）。"""
    sp = e.data["Player"]["StockPos"]
    for p in sp:
        if p.get("Code") == code:
            old_vol = p.get("VolumeUsable", 0)
            e.data["Player"]["StockPos"] = [p for p in sp if p.get("Code") != code]
            return old_vol
    return None


def set_player_amount(e, amount):
    """修改玩家总资金 Player.Amount。"""
    e.data["Player"]["Amount"] = amount


def sync_npc_holdings(stock, delta, target, hot=None):
    """玩家持仓变化 delta(=new-old) 后，同步 NPC 持仓（筹码守恒 + 智能增发）。

    - target: 过户对象 dict（inst/ret/hot 之一）。target=None 表示不同步（凭空）。
    - delta>0：玩家加仓，NPC 减少；缺口触发增发。
    - delta<0：玩家减仓，NPC 增加。
    - NPC 可卖为 -1（无限制）时不增不减、不增发。
    返回 (action, info)：
        ("unlimited", None)         NPC 无限制，无需变动
        ("diluted", shortage)       触发增发，补了 shortage 股
        ("reduced", new_npc_vol)    NPC 普通扣减
        ("increased", new_npc_vol)  NPC 普通增加
        ("noop", None)              target 为空或 delta==0
    """
    if target is None or delta == 0:
        return ("noop", None)
    cur_npc_vol = target.get("VolumeUsableSell", 0)
    if cur_npc_vol == -1:
        return ("unlimited", None)
    if delta > 0:  # 玩家买入，NPC 减少
        shortage = delta - cur_npc_vol
        if shortage > 0:
            dilute_for_shortage(stock, shortage)
            target["VolumeUsableSell"] = 0
            return ("diluted", shortage)
        target["VolumeUsableSell"] = cur_npc_vol - delta
        return ("reduced", target["VolumeUsableSell"])
    else:  # 玩家卖出(delta<0)，NPC 增加
        target["VolumeUsableSell"] = cur_npc_vol + abs(delta)
        return ("increased", target["VolumeUsableSell"])
