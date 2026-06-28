# 主力模拟器存档修改器

Steam 游戏 **《主力模拟器》（StocksMainForceSimulator，开发商 LoneCat）** 的存档修改工具。

支持 **三种前端**，共享同一套 `src/core` 纯业务后端：

- **TUI**（交互式终端菜单）—— 主力前端，菜单结构为「主菜单（全局）→ 单只股票子菜单」
- **CLI**（非交互式子命令）—— 可脚本化/批处理
- **GUI**（pytauri + React 桌面端，Windows WebView2）—— 图形界面

```
src/
  core/          # 纯业务后端（仅标准库，三前端共享）；extra/ 放社区贡献的 extra 功能
  tui/           # 交互式终端前端：frontend/app.py（= sse 交互壳）+ backend（纯辅助）
  cli/cli.py     # 非交互式命令行前端
  gui/           # pytauri 桌面端：backend 命令层 + React 前端 + 启动器
```

## 特性

**核心功能（原主干）：**

- 🎯 **单股精修**：市盈率（PE）、市净率（PB）、负债率、发行价、昨收盘价、涨跌停幅度、主力/散户挂单数量、自由设定全部财务指标（防回滚）
- 🌐 **全局调控**：NPC 购买取向（推高个股 / 推高板块 / 拉升 / 砸盘）、玩家持仓（带筹码守恒与智能增发）、总资金
- 🧹 **存档瘦身**：清空公告历史、裁剪机构持仓、清空交易历史，减小文件体积、提升游戏性能
- 🛡️ **进程防覆盖**：保存前检测游戏是否在运行并警告，避免被游戏自动保存覆盖
- 💾 **自动备份**：每次保存前自动生成带时间戳的备份（`.sav.bak.YYYYMMDD_HHMMSS`）
- 🎨 **彩色终端界面**，带输入校验（范围 / 类型）和确认提示，降低误操作风险
- 📦 **零依赖**：core / cli / tui 仅使用 Python 标准库（GUI 的 pytauri 为可选 extra）

**Extra 功能（社区贡献，下文 [Extra 功能](#extra-功能) 单列）：** 发行/退市股票、发布公告与业绩报告、股票分红（现金/送股）、定向增发、市场整顿（筹码守恒）、全市场砍机构转散户。

## 环境要求

- Windows 10 / 11（存档位于 Windows 的 `AppData` 目录）
- Python 3.11+（core / cli / tui）
- GUI 额外需要：Node.js（构建前端）+ Windows WebView2 运行时（Win11 自带）；`pytauri-wheel` 提供预构建 wheel，**无需 Rust 工具链**

## 快速开始

### TUI（交互式终端）

```bash
python -m src.tui.frontend.app            # 也可用打包入口 sse-tui
python -m src.tui.frontend.app -d <存档目录>
```

启动后按提示操作：

1. **选择存档目录** —— 自动扫描默认存档目录下的子文件夹
2. **选择存档文件** —— 列出所有 `.sav` 文件（含大小和修改时间）
3. **进入主菜单** —— 选择全局操作，或进入某只股票的子菜单

### CLI（非交互式子命令）

```bash
python -m src.cli.cli list-saves -d <存档目录>
python -m src.cli.cli set-pe 2001 5.0 --save <文件.sav> --yes
python -m src.cli.cli rectify --save <文件.sav>           # [extra] 市场整顿
python -m src.cli.cli --help                               # 查看全部子命令
```

### GUI（pytauri 桌面端）

```bash
pip install -e ".[gui]"                 # 装 pytauri-wheel（免 Rust）
cd src/gui/frontend && npm install      # 装前端依赖
npm run dev                             # 开发模式：Vite dev server + HMR
# 另开终端：
DEV_SERVER=http://localhost:5173 python -m src.gui.app

# 生产模式：
npm run build                           # 产物输出到 src/gui/dist-frontend/
python -m src.gui.app                   # 直接加载构建产物
```

### 默认存档位置

```
%USERPROFILE%\AppData\LocalLow\LoneCat\StocksMainForceSimulator\Saves\
```

即：`C:\Users\<你的用户名>\AppData\LocalLow\LoneCat\StocksMainForceSimulator\Saves\`

程序通过 `Path.home()` 自动定位，无需手动配置。

## 一键脚本（`scripts/`）

Windows 上双击或 cmd/PowerShell 跑（都是 `.bat` 脚本）。**dev 免编译、与打包共用同一份 core/后端/前端，强一致**。

| 脚本 | 作用 |
|---|---|
| `scripts\dev.bat tui [存档目录]` | 免编译预览 TUI |
| `scripts\dev.bat cli <子命令> [参数]` | 免编译预览 CLI（如 `list-saves`、`--help`） |
| `scripts\dev.bat gui` | **免 Rust** 预览 GUI（pytauri-wheel + Vite HMR，秒起） |
| `scripts\test.bat [模块]` | 直接跑测试（全量或单模块，免打包） |
| `scripts\build-gui.bat` | 打包 GUI → `build\bundle-release\` 的 `.msi`/`.exe`（standalone，需 Rust） |
| `scripts\build-tui.bat` | 打包 TUI → `build\pyi-dist\sse-tui.exe`（PyInstaller 单文件，需 Python） |
| `scripts\build-cli.bat` | 打包 CLI → `build\pyi-dist\sse-cli.exe`（PyInstaller 单文件，需 Python） |
| `scripts\clean.bat [--deep]` | 清理产物；`--deep` 连依赖一起清 |

> 旧脚本 `run-tui.bat`/`run-cli.bat`/`run-gui.bat` 仍保留（`dev.bat` 是它们的统一入口）。

GUI 两种运行模式共享同一份 `src/core` + `src/gui/backend/commands.py` + 前端：
- **dev**（`dev.bat gui`）：`pytauri-wheel` 当 Python 库，`pip install pytauri-wheel`（预构建，**免 Rust**）后直接跑，前端用 Vite dev server（HMR）。改 Python 重跑、改前端秒级生效。
- **打包**（`build-gui.bat`）：standalone pytauri（Rust crate + 嵌入 python-build-standalone），出原生 `.msi`/`.exe`。

GUI 预览/打包前提（首次）：Rust(MSVC) + `uv` + Node。`build-gui.bat` 会自动下载嵌入 Python（python-build-standalone）。

**下载 Release 产物**（[Releases 页](https://github.com/msuadOf/stock_emu_cheet/releases)）：
- **安装版（推荐）**：`*-setup.exe`（NSIS）或 `.msi`，双击安装后从开始菜单运行。
- **免安装 / 绿色版**：`*-portable.zip`，解压到任意目录，双击里面的 `sse-gui.exe` 即用（内置 Python 与依赖，不依赖系统装 Python）。
- ⚠️ `sse-gui.exe` 依赖同目录的嵌入 Python，**必须和 zip 解压出的其他文件放一起**，不要单独拿出来双击。

**下载走代理**（首次打包时下载 python-build-standalone、npm/uv/cargo 拉依赖，国内网络常需代理）：

```bat
scripts\build-gui.bat --proxy http://localhost:7888
```

或先设环境变量再跑：

```bat
set PROXY=http://localhost:7888
scripts\build-gui.bat
```

`--proxy` 会同时：① 给 `curl`（下载嵌入 Python）加 `--proxy`；② 导出 `HTTP_PROXY`/`HTTPS_PROXY` 给 npm/uv/cargo 用。

## CI / 发版（GitHub Actions）

- **测试**：`test.yml`，push/PR 到 `main`/`dev`/`dev-refactor` 时在 Windows 跑 `run_tests.py`。
- **发版**：`release.yml`，两种触发方式：
  - **手动**：Actions 页 → release → Run workflow，填版本号（如 `0.3.0`）。
  - **打 tag**：`git tag v0.3.0 && git push origin v0.3.0` 自动发版。
  - 流程：装 Rust+Node+uv → 跑测试 → `build-gui.bat` 打包 → 把 `.msi`/`.exe` 上传到 GitHub Release。

## 功能说明

### GUI 批量操作（持仓）

GUI 左侧股票列表支持多选：**点行 = 选中**、**Shift+点行 = 区间多选**（从上次点的到当前，正序逆序均可）、勾选框 = 增删单只、表头勾选框 = 全选。批量操作区在选中 ≥1 只时都显示（单股时也显示在单股表单下方）。

**批量改持仓**：把玩家对所选股票的持仓统一设为「各自流通股 × pct%」。扣仓位时筹码守恒（从对应账户可卖里扣减/回补，不增发、不超扣，不足记 `shortfall`）。扣仓位策略 6 选 1：

| 策略 | 说明 |
|------|------|
| 优先主力 `inst` | 先扣主力，不够扣散户（默认） |
| 优先散户 `ret` | 先扣散户，不够扣主力 |
| 优先游资 `hot` | 先扣游资，不够扣主力→散户（修了原版 hot 失效的 bug） |
| 主力+散户按比例均衡 `balance_ir` | 按各自可卖筹码占比分摊 |
| 先散户后机构 `ret_then_inst` | 先散户、再机构，游资最后兜底 |
| 5 类 NPC 按比例均匀扣 `npc_proportional` | 遍历 AloneNpc/HuddleNpc/MessageNpc/RelayNpc/SneakNpc 按可卖比例扣（不碰主力/散户/游资） |

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

> ⭐ 标记的为 **[Extra 功能](#extra-功能)**。

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

> ⭐ 标记的为 **[Extra 功能](#extra-功能)**。

## Extra 功能

以下功能来自社区贡献者的 fork（PR #2），经「批判性合并」移植进来，**在代码中每个相关函数上方都标注了 `# [extra]` 注释**（核心逻辑物理隔离在 `src/core/extra/`），便于区分原主干功能。合并时已修复原 fork 的若干 100× 缩放 bug（详见下文「已知修复」）。

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

> **内部辅助函数**（不直接出现在菜单，被上述功能调用，同样标注 `# [extra]`）：`get_current_game_day`、`get_or_create_delisted_pool`、`_filter_delisted_candidates`、`_build_stock_notice`、`_print_notice_preview`、`_append_notice_normal`、`_create_stock_performance`、`_view_notice_list`、`show_notice_detail`、`show_report_detail`。

### 已知修复（合并时纠正的缩放 bug）

游戏存档约定：**内部值 = 显示值 × 100**（价格以"分"存、股数/金额 ×100 存）。原 fork 多处漏了 `/100`，合并时已修正：

- `change_pe` / `change_pb` / `show_stock`：改走 `calc_pe` / `calc_pb` 助手（原 fork 内联公式漏 `/100`，PE/PB 会大 100×）
- `_create_stock_performance`：PE/PB = `PriceFact×VolumeTotal/(100×NetProfit)`
- `private_placement`：增发股数 `ns = amt_y/py×100`（原 fork 写成 `amt_y/(py×100)`，差 10000×）
- `stock_dividend` 现金分红：`max_D` / 每户派现 / 总分红额用 `/10000` 缩放，除息价跌 `D`（分）；并修复了现金分红误改总股本、`choice==3` 复用送股前旧值两处逻辑 bug
- `issue_stock`：`VolumeTotal` / `VolumeFlow` 改存内部值（原 fork 直接存显示股/手数，导致新发股票与全市场不一致）
- 新增 `SECTOR_MAP` / `BOURSE_MAP` 模块级常量（`publish_notice` 依赖）

## ⚠️ 使用须知

- **务必备份**：虽然程序会自动备份，建议首次使用前手动复制一份完整存档目录以防万一。
- **关闭游戏**：修改存档前请先完全退出游戏，避免存档被游戏覆盖或损坏。
- **风险自担**：本工具为单机游戏的数据修改用途，与联机 / 排行榜无关。因修改造成的存档损坏请从备份恢复。
- 修改后未保存的更改会显示 `* UNSAVED *` 提示，退出前会再次确认。

## 技术细节

- **分层架构**（依赖严格单向，禁止环依赖）：`cli → core`、`tui → core`、`gui/backend → core`。`src/core` 是纯业务后端，只依赖标准库，**绝不** import tui/cli/gui。社区贡献的 extra 功能物理隔离在 `src/core/extra/`（注释标 `# [extra]`）。
- **三前端共享 core**：TUI 的交互式菜单、CLI 的子命令、GUI 的 pytauri 命令层，都调用同一套 `src/core` 纯函数，逻辑不重复。
- **GUI**：`src/gui/backend/commands.py` 是 pytauri `@commands.command()` 命令层（依赖 core），前端为 `src/gui/frontend`（React + Vite + TypeScript），通过 `window.__TAURI__.pytauri.pyInvoke` 调 backend。用 `pytauri-wheel` 预构建 wheel，免 Rust 工具链；Windows 上用系统 WebView2（不打包 Chromium，体积小）。
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
python run_tests.py tests.test_v2_features # 只跑 extra 功能的缩放回归测试（文件名沿用历史命名）
python run_tests.py tests.test_core_ops   # core 纯函数单元测试
python run_tests.py tests.test_core_extra # extra 纯函数单元测试
```

测试全程在内存虚拟存档 / 临时文件上运行，**绝不会触碰真实的 `.sav` 存档**。退出码 0 表示全部通过，非 0 表示有失败，可结合 CI 或脚本判断。`run_tests.py` 本质是标准库 `unittest` 的包装器——跑同一批用例、发现/断言/通过判定完全一致，只是额外做了三件事：强制 UTF-8 输出（绕开中文 Windows 的 GBK 编码报错）、追加中文通过率摘要、`-v` 和模块名参数更宽松。需要精确到单个测试类/方法调试时（如 `python -m unittest tests.test_features.TestUnitScaling`）可临时退回原生 `unittest`，但若有中文输出仍建议用 `run_tests.py`。

## 许可

仅供学习与个人单机娱乐使用。
