---
name: build-and-deploy
description: 本项目编译/打包/部署指南——三前端(dev免编译/打包)、pytauri standalone 出 .msi/.exe、GitHub Actions 发版、×100/白屏/ABI 等已知坑。打包或发版前必读。
---

# 编译打包部署（stock_emu_cheet）

## 三前端运行方式

| 前端 | dev（免编译） | 打包 |
|---|---|---|
| TUI | `scripts/dev.sh tui` | （无独立包，含在 Python 项目） |
| CLI | `scripts/dev.sh cli <子命令>` | （无独立包） |
| GUI | `scripts/dev.sh gui`（pytauri-wheel，**免 Rust**） | `scripts/build-gui.sh`（standalone，出 .msi/.exe） |

## 快速验证（不打包）
```bash
scripts/test.sh                 # 全量测试
scripts/dev.sh tui              # 跑 TUI
scripts/dev.sh cli list-saves   # 跑 CLI
scripts/dev.sh gui              # 跑 GUI（vite HMR + pytauri-wheel，免 Rust）
```

## GUI 打包（standalone pytauri → .msi/.exe）
```bash
scripts/build-gui.sh            # 产物在 build/bundle-release/
```
- 前提：**VS 2022 BuildTools + VC++ 桌面开发工作负载**（提供 cl.exe/link.exe/SDK）、Rust(stable-msvc)、tauri-cli、uv、Node。
- 产物：`build/bundle-release/{sse-gui.exe, bundle/msi/*.msi, bundle/nsis/*-setup.exe}`。
- 输出目录由 `src-tauri/.cargo/config.toml` 的 `target-dir="../build"` 控制，整个 `build/` 已 gitignore。

## 发版（GitHub Actions）
- 测试：push/PR 到 main/dev/dev-refactor → `test.yml`（Windows 跑 run_tests.py）。
- 发版 `release.yml`，两种触发：
  - 手动：Actions → release → Run workflow，填版本号。
  - tag：`git tag v0.3.0 && git push origin v0.3.0`。
  - 流程：装 Rust+Node+uv → 测试 → build-gui.sh → 上传 .msi/.exe 到 Release。

## 已知坑（踩过，别再踩）

1. **×100 单位**：内部值=显示值×100。**只通过 SaveModel getter/setter 访问字段**，别手写 /100。见 [[coding-principles]]。
2. **白屏根因（pytauri #110）**：`tauri-plugin-pytauri` 必须是 Cargo.toml **直接依赖**（传递依赖不够），capabilities 要 `pytauri:default`，前端用 `import { pyInvoke } from 'tauri-plugin-pytauri-api'`（别用 `window.__TAURI__.pytauri`）。否则 JS import 时崩 → 白屏。
3. **GUI ABI 必须 MSVC**：PyO3/Python 是 MSVC ABI，Rust 必须用 `x86_64-pc-windows-msvc` target。**GNU target 对 pytauri 是死路**。所以必须装 VS BuildTools 的 VC++ 工作负载（光装 BuildTools 壳不够）。
4. **打包前杀残留 exe**：跑着的 sse-gui.exe 占着 pyembed 的 DLL，rebuild 报 os error 32。build-gui.sh 已自动 taskkill。
5. **standalone 命令参数名**：`@commands.command()` 只允许 `body`/`app_handle`/`webview_window`/`headers`/`Annotated`。裸参数名报错 → 用单个 `body: dict`。

## dev vs 打包 的一致性
两者共用 `src/core` + `src/gui/backend/commands.py` + `src/gui/frontend`。dev 用 pytauri-wheel（Python 当库，免 Rust），打包用 standalone（Rust crate 主导 + 嵌入 python-build-standalone）。同一份 backend 代码两条路径，改一处都生效。
