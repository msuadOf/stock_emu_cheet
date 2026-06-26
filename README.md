# 主力模拟器存档修改器

Steam 游戏 **《主力模拟器》（StocksMainForceSimulator，开发商 LoneCat）** 的存档修改工具。

一个纯终端（TUI）的交互式存档编辑器，支持任意存档、任意股票的改档操作。菜单结构为：

```
主菜单（全局操作）
  └── 选择单只股票 → 单个股票菜单（价格 / 估值 / 挂单 …）
```

## 特性

**核心功能（原主干）：**

- 🎯 **单股精修**：市盈率（PE）、市净率（PB）、负债率、发行价、昨收盘价、涨跌停幅度、主力/散户挂单数量、自由设定全部财务指标（防回滚）
- 🌐 **全局调控**：NPC 购买取向（推高个股 / 推高板块 / 拉升 / 砸盘）、玩家持仓（带筹码守恒与智能增发）、总资金
- 🧹 **存档瘦身**：清空公告历史、裁剪机构持仓、清空交易历史，减小文件体积、提升游戏性能
- 🛡️ **进程防覆盖**：保存前检测游戏是否在运行并警告，避免被游戏自动保存覆盖
- 💾 **自动备份**：每次保存前自动生成带时间戳的备份（`.sav.bak.YYYYMMDD_HHMMSS`）
- 🎨 **彩色终端界面**，带输入校验（范围 / 类型）和确认提示，降低误操作风险
- 📦 **零依赖**：仅使用 Python 标准库

**Extra 功能（v2 贡献，下文 [Extra 功能](#extra-功能v2-贡献) 单列）：** 发行/退市股票、发布公告与业绩报告、股票分红（现金/送股）、定向增发、市场整顿（筹码守恒）、全市场砍机构转散户。

## 环境要求

- Windows 10 / 11（存档位于 Windows 的 `AppData` 目录）
- Python 3.6+

## 快速开始

```bash
python stock_save_editor.py
```

启动后按提示操作：

1. **选择存档目录** —— 自动扫描默认存档目录下的子文件夹
2. **选择存档文件** —— 列出所有 `.sav` 文件（含大小和修改时间）
3. **进入主菜单** —— 选择全局操作，或进入某只股票的子菜单

### 默认存档位置

```
%USERPROFILE%\AppData\LocalLow\LoneCat\StocksMainForceSimulator\Saves\
```

即：`C:\Users\<你的用户名>\AppData\LocalLow\LoneCat\StocksMainForceSimulator\Saves\`

程序通过 `Path.home()` 自动定位，无需手动配置。

## 功能说明

### 单只股票菜单

| 选项 | 功能 | 说明 |
|------|------|------|
| 1 | 查看完整详情 | 价格、公司信息、财务指标、主力机构、散户、最近 5 根 K 线 |
| 2 | 改市盈率 PE | 通过调整净利润反推 PE；PE 越小越"安全" |
| 3 | 改市净率 PB | 通过调整净资产反推 PB |
| 4 | 改负债率 | 通过调整总负债控制资产负债率 |
| 5 | 改发行价 PriceInit | 涨跌停的计算基准 |
| 6 | 改昨收/开盘价 PriceFact | 今日价格波动起点（带 K 线同步） |
| 7 | 改涨跌停幅度 RateLimit | 控制每日价格波动剧烈程度 |
| 8 | 改主力/散户挂单 | 影响五档买卖盘流动性 |
| 9 | 改财务指标 | 自由设定所有财务字段（防回滚） |
| 10 ⭐ | 查看公告/业绩报告 | 该股的 NoticeNormal / NoticeReport |
| 11 ⭐ | 发布公告 | 为该股发布公告或业绩报告 |
| 12 ⭐ | 该股分红 | 现金分红 / 送股 / 先送后现 |
| 13 ⭐ | 该股定向增发 | 按近 20 日均价 × 折价率 |
| 0 | 返回主菜单 | |

> ⭐ 标记的为 **[Extra 功能（v2 贡献）](#extra-功能v2-贡献)**。

> **价格内部值提示**：游戏内部价格为显示价的 100 倍。例如 `PriceFact=100000` 对应显示价 `1000.00 元`。修改时直接输入显示价（元），程序会自动换算。

### 主菜单（全局操作）

| 选项 | 功能 | 说明 |
|------|------|------|
| 1 | 操作单个股票 | 进入子菜单 |
| 2 | 查看所有股票列表 | 代码 + 昨收价一览（只读） |
| 3 | 改购买取向 NoticeStyle | NPC 买入/卖出力度（全局） |
| 4 | 改玩家持仓 Player.StockPos | 带筹码守恒与智能增发 |
| 5 ⭐ | 发行新股票 | 退市池恢复 或 自定义代码发行 |
| 6 ⭐ | 股票退市 | A 集合警告退市 / B 集合完全退市 |
| 7 ⭐ | 发布公告 | 市场/板块/股票公告 或 业绩报告 |
| 8 ⭐ | 股票分红 | 现金分红 / 送股 / 先送后现 |
| 9 ⭐ | 定向增发 | 按近 20 日均价 × 折价率 |
| 10 ⭐ | 市场整顿 | 强制 sum_hold == VolumeFlow（筹码守恒） |
| 11 ⭐ | 砍机构持仓转散户 | 全市场 NPC 持仓转入散户 |
| 12 | 清空公告历史 NoticeGroup | 减小文件 |
| 13 | 裁剪机构持仓 HuddleNpc | 提升性能 |
| 14 | 清空交易历史 TradeType | |
| 15 | 保存 | 自动备份 + 进程防覆盖检测 |
| 16 | 重新加载 | 放弃内存修改，从磁盘重读 |
| 17 | 退出 | 有未保存修改时会二次确认 |

> ⭐ 标记的为 **[Extra 功能（v2 贡献）](#extra-功能v2-贡献)**。

## Extra 功能（v2 贡献）

以下功能来自社区贡献者的 fork（PR #2），经「批判性合并」移植进来，**在代码中每个相关函数上方都标注了 `# [v2 extra]` 注释**，便于区分原主干功能。合并时已修复 v2 原版的若干 100× 缩放 bug（详见下文「已知修复」）。

| 功能 | 入口 | 说明 |
|------|------|------|
| **发行新股票** `issue_stock` | 主菜单 5 | 两种来源：① 从退市池 B 集合恢复（无初始持仓，自定义财务）；② 自定义代码发行（主力 51% / 散户 49% 初始仓位，自动推断交易所/板块，生成初始 K 线，写入 `Name.sav`、挂接 `Sectors`） |
| **股票退市** `delist_stock` | 主菜单 6 | ① A 集合：警告式退市（限 5% 涨跌停）；② B 集合：完全退市（移出股票池、清除公告、清玩家持仓、计入损失）；③ 可按负债率+连续亏损自动筛选候选；④ 强制退市任意代码。维护 `Market.DelistedPool = {A, B}` |
| **发布公告** `publish_notice` | 主菜单 7 / 子菜单 11 | ① 市场公告（Code=0）；② 板块公告；③ 股票公告（支持批量逗号分隔）；④ 业绩报告 `NoticeReport`（可按涨幅或绝对值，自动同步该股财务与 PE/PB） |
| **查看公告** `view_notices` | 子菜单 10 | 浏览该股的 `NoticeNormal` / `NoticeReport`，可查看详情或按索引删除 |
| **股票分红** `stock_dividend` | 主菜单 8 / 子菜单 12 | ① 现金分红（每手 D 元/100 股，全员派现、除息、扣净资产，受负债率 70% 限制）；② 送股（10 送 X，按比例放大持仓、降价、市值不变）；③ 先送后现。自动同步全部账户 |
| **定向增发** `private_placement` | 主菜单 9 / 子菜单 13 | 增发价 = 近 20 日均价 × 折价率；玩家支付金额认购新增流通股，扣减玩家总资金，首笔自动登记交易记录 |
| **市场整顿** `market_rectification` | 主菜单 10 | 逐只股票强制 `主力+散户+NPC+玩家 == VolumeFlow`：差异小按顺序扣减，差异大按比例缩放，差异为负补主力，兜底改 `VolumeFlow` |
| **砍机构转散户** `change_npc_all_to_retail` | 主菜单 11 | 全市场扫描 5 类 NPC（Alone/Huddle/Message/Relay/Sneak）持仓，汇总转入对应股票的散户 `VolumeUsableSell`，并做筹码守恒平账 |

> **内部辅助函数**（不直接出现在菜单，被上述功能调用，同样标注 `# [v2 extra]`）：`get_current_game_day`、`get_or_create_delisted_pool`、`_filter_delisted_candidates`、`_build_stock_notice`、`_print_notice_preview`、`_append_notice_normal`、`_create_stock_performance`、`_view_notice_list`、`show_notice_detail`、`show_report_detail`。

### 已知修复（合并时纠正的 v2 bug）

游戏存档约定：**内部值 = 显示值 × 100**（价格以"分"存、股数/金额 ×100 存）。v2 原版多处漏了 `/100`，合并时已修正：

- `change_pe` / `change_pb` / `show_stock`：改走 `calc_pe` / `calc_pb` 助手（v2 内联公式漏 `/100`，PE/PB 会大 100×）
- `_create_stock_performance`：PE/PB = `PriceFact×VolumeTotal/(100×NetProfit)`
- `private_placement`：增发股数 `ns = amt_y/py×100`（v2 写成 `amt_y/(py×100)`，差 10000×）
- `stock_dividend` 现金分红：`max_D` / 每户派现 / 总分红额用 `/10000` 缩放，除息价跌 `D`（分）；并修复了现金分红误改总股本、`choice==3` 复用送股前旧值两处逻辑 bug
- `issue_stock`：`VolumeTotal` / `VolumeFlow` 改存内部值（v2 直接存显示股/手数，导致新发股票与全市场不一致）
- 新增 `SECTOR_MAP` / `BOURSE_MAP` 模块级常量（`publish_notice` 依赖）

## ⚠️ 使用须知

- **务必备份**：虽然程序会自动备份，建议首次使用前手动复制一份完整存档目录以防万一。
- **关闭游戏**：修改存档前请先完全退出游戏，避免存档被游戏覆盖或损坏。
- **风险自担**：本工具为单机游戏的数据修改用途，与联机 / 排行榜无关。因修改造成的存档损坏请从备份恢复。
- 修改后未保存的更改会显示 `* UNSAVED *` 提示，退出前会再次确认。

## 技术细节

- 存档格式为 JSON，程序以 `utf-8` 读写，输出时保留中文（`ensure_ascii=False`）并紧凑格式化。
- Windows 下自动启用控制台 ANSI 颜色支持（`SetConsoleMode`）。
- 大额数字会自动标注"万 / 亿"单位，便于阅读。

## 测试

本项目使用 `run_tests.py` 作为统一回归测试入口（**不是** `pytest` / `python -m unittest`，请勿混用）。它做了几件事：Windows 控制台强制 UTF-8 输出（避免中文/emoji 乱码）、跑完后打印中文通过率摘要、支持只跑某个模块。

```bash
python run_tests.py                    # 跑全部测试（默认 discover tests/ 下所有 test_*.py）
python run_tests.py -v                 # 详细模式（每个用例一行）
python run_tests.py tests.test_cli     # 只跑 CLI 接口测试
python run_tests.py tests.test_features # 只跑 feat 点测试
python run_tests.py tests.test_v2_features # 只跑 v2 extra 功能的缩放回归测试
```

测试全程在内存虚拟存档 / 临时文件上运行，**绝不会触碰真实的 `.sav` 存档**。退出码 0 表示全部通过，非 0 表示有失败，可结合 CI 或脚本判断。`run_tests.py` 本质是标准库 `unittest` 的包装器——跑同一批用例、发现/断言/通过判定完全一致，只是额外做了三件事：强制 UTF-8 输出（绕开中文 Windows 的 GBK 编码报错）、追加中文通过率摘要、`-v` 和模块名参数更宽松。需要精确到单个测试类/方法调试时（如 `python -m unittest tests.test_features.TestUnitScaling`）可临时退回原生 `unittest`，但若有中文输出仍建议用 `run_tests.py`。

## 许可

仅供学习与个人单机娱乐使用。
