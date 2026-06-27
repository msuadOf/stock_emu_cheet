---
name: coding-principles
description: 本项目编码原则——单一数据访问层(SaveModel)、×100单位收口、分层无环依赖、测试驱动。改 core 业务代码或加新功能前必读。
---

# 编码原则（stock_emu_cheet）

## 1. 单一字段访问层：SaveModel（铁律）

所有存档字段访问**只许**通过 `src/core/savemodel.py` 的 model getter/setter。
**禁止**在业务代码里直接读写字段裸 dict（`info["PriceFact"]`）。

- **为什么**：游戏内部值 = 显示值 × 100，散落各处必踩 100× bug（已踩多次）。
- **怎么用**：`info.price_fact`（getter 返回显示元）/ `info.price_fact = 12.34`（setter 内部 ×100）。
- **例外**（用 `*_raw`）：哨兵 `-1`（无限）必须用 `volume_usable_sell_raw` 检测（getter 会变 -0.01）；Candles.Volume 是「手(lots)」用 `volume_lots`/`volume_shares`，**不是** ×100。
- 不缩放字段（Code/RateLimit 小数/Limit/Bourse/Sector/Day）原样。

## 2. 分层与依赖方向（不可违反）

```
cli → core ← tui(app.py)
gui/frontend → gui/backend → core
```
- `src/core` 只依赖标准库，**绝不** import tui/cli/gui。否则环依赖。
- 两个「backend」：`src/core`=共享业务后端；`src/gui/backend`=GUI 专属 pytauri 命令层（依赖 core）。

## 3. 测试驱动，保持绿

- 改 core 函数 → 同步改对应测试（`tests/test_core_*.py`），用 `scripts\test.bat` 验证全绿。
- 测试用 `tests/helpers.py` 的 `make_stock`/`make_save` 造数据，包成 `SaveModel.from_dict(...)`。
- 提交前必跑 `scripts\test.bat`，绿才提交。

## 4. extra 功能统一标 `extra`（不要用 v2）

社区贡献功能（公告/退市/增发/分红/市场整顿）物理隔离在 `src/core/extra/`，注释标 `# [extra]`。
**绝不**用「v2」字样（已废除的错误概念）。

## 5. dev 与打包共用代码（强一致性）

`scripts\dev.bat`（免编译预览）和 `scripts\build-gui.bat`（打包）用的是**同一份** `src/core` + `src/gui/backend/commands.py` + 前端。改一处两端生效，无需为 dev 单独维护副本。

## 6. 批量改持仓的扣仓位策略（`batch_set_player_pct`）

`src/core/player_ops.py` 的 `batch_set_player_pct(save, codes, pct, target_account="inst", strategy=None)`。
`strategy` 优先于 `target_account`（二者等价、旧调用传 target_account 仍兼容）。6 种策略：
- `inst`/`ret`/`hot`：按该优先顺序依次扣（不够扣下一个；hot 兜底到 inst/ret）。
- `balance_ir`：主力+散户按各自可卖筹码**比例均衡**分摊。
- `ret_then_inst`：先散户、后机构，游资最后兜底。
- `npc_proportional`：遍历 5 类 NPC（`stock.npc_accounts(kind)`，kind ∈ NPC_KEYS）按可卖比例扣。

**单位**：全程显示股（流通股 `info.volume_flow`、可卖 `account.volume_usable_sell`），×100 由 setter 处理。
筹码守恒：玩家加仓从对应账户扣、减仓回补，**不增发**；不足如实记 `shortfall_shares`，玩家仍获目标持仓。
返回 `{code: {volume, volume_raw, taken_from, action, shortfall_shares, sellable_ratio_pct}}`。
改策略逻辑必同步改 `tests/test_core_batch.py::TestBatchStrategies`，断言用 `r[code]["volume"]` 守恒（勿手算单位）。
