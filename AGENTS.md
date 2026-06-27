# AGENTS.md — 项目协作约定

> Steam 游戏《主力模拟器》存档编辑器。CLI / TUI / GUI 三前端共享 `src/core` 纯业务后端。
> 详细技能见 `.claude/skills/`（`coding-principles`、`build-and-deploy`）。

## 架构（分层，依赖单向，禁止环）

```
src/core/          纯业务后端（仅标准库）—— 三前端共享
  savemodel.py     ★ 唯一字段访问层（getter/setter，×100 收口）
  stock_ops/player_ops/extra/*   业务函数（收 SaveModel/InfoModel）
  editor.py        Editor 纯落盘层（load→SaveModel / save）
  calcs.py         PE/PB/市值/格式化（纯函数）
src/tui/app.py     交互式终端（= 测试加载的 sse 模块；交互 Editor 留此兼容测试）
src/cli/cli.py     非交互式子命令
src/gui/           pytauri 桌面端：backend/commands.py + app.py(打包) + app_dev.py(dev免Rust) + frontend(React)
src-tauri/         Rust crate（standalone 打包用；dev 模式不需要）
```
`core` **绝不** import tui/cli/gui。

## 铁律：单一字段访问层

游戏内部值 = 显示值 × 100。**所有字段访问只走 `SaveModel` 的 getter/setter**，禁止裸 dict。
- `info.price_fact`（显示元）/ `info.price_fact = 12.34`（内部自动 ×100）
- 哨兵 `-1`（无限）用 `*_raw`；Candles.Volume 是「手」用 `volume_lots`/`volume_shares`（非 ×100）
- 不缩放：Code/RateLimit(小数)/Limit/Bourse/Sector/Day

## 常用命令

```bash
scripts/test.sh                 # 测试（提交前必跑，绿才提交）
scripts/dev.sh tui|cli|gui      # 免编译预览（GUI 用 pytauri-wheel，免 Rust）
scripts/build-gui.sh            # 打包 GUI → build/bundle-release/ 的 .msi/.exe
scripts/clean.sh [--deep]       # 清理产物
```

- dev 与打包**共用同一份** `src/core` + `src/gui/backend/commands.py` + 前端，强一致。
- GUI dev：`scripts/dev.sh gui`（pytauri-wheel 模式，免 Rust，vite HMR）。
- GUI 打包：`scripts/build-gui.sh`（standalone pytauri，需 VS BuildTools+VC++ + Rust+MSVC）。

## 约定

- **extra 功能**（公告/退市/增发/分红/市场整顿）在 `src/core/extra/`，注释标 `# [extra]`。**不用「v2」**（已废除的错误概念）。
- 改 core 函数 → 同步改 `tests/test_core_*.py`，用 `make_stock`/`make_save` 造数据包 `SaveModel.from_dict(...)`。
- 入口：`python -m src.{tui.app, cli.cli, gui.app_dev}`；打包 exe 由 `build-gui.sh` 产出。
- 入口脚本/CI 见 `scripts/` 与 `.github/workflows/`（test.yml + release.yml，release 手动或 tag v* 触发）。

## 已知坑（详见 .claude/skills/build-and-deploy）
×100 单位、GUI 白屏(pytauri #110)、GUI ABI 必须 MSVC（GNU 不行）、打包前杀残留 exe、standalone 命令参数只能用 `body`。
