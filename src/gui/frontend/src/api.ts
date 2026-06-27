// pyInvoke 封装层：与 src/gui/backend/commands.py 的 @commands.command() 一一对应。
// 通过官方 JS 绑定 `tauri-plugin-pytauri-api` 调用后端命令。
// 注意：必须 import 这个包，不能直接用 window.__TAURI__.pytauri（那样会 undefined 导致白屏）。

import { pyInvoke } from 'tauri-plugin-pytauri-api';

export interface StockSummary {
  code: number;
  price_init: number;
  price_fact: number;
  rate_limit: number;
  volume_total: number;
  volume_flow: number;
  market_cap: number;
  pe: number | null;
  pb: number | null;
}

function invoke<T>(cmd: string, args: Record<string, unknown>): Promise<T> {
  // 第二个参数作为后端 command 的 body（commands.py 里统一用 body: dict）
  return pyInvoke<T>(cmd, args);
}

export const api = {
  // ---- 存档定位（默认目录 + 槽 + 文件选择器）----
  getDefaultSave: () => invoke<{ default_dir: string }>('get_default_save', {}),
  listSlots: (dir?: string) => invoke<{ slots: { name: string; path: string; file_count: number }[] }>('list_slots', dir ? { dir } : {}),
  listFiles: (dir: string) => invoke<{ files: { name: string; path: string; size_kb: number; modified: string }[] }>('list_files', { dir }),

  // ---- 主干 ----
  listStocks: (file: string) => invoke<{ stocks: StockSummary[]; count: number }>('list_stocks', { file }),
  getStock: (file: string, code: number) => invoke<StockSummary & { error?: string }>('get_stock', { file, code }),
  setPe: (file: string, code: number, target: number, save = true) =>
    invoke<StockSummary>('set_pe', { file, code, target, save }),
  setPb: (file: string, code: number, target: number, save = true) =>
    invoke<StockSummary>('set_pb', { file, code, target, save }),
  setDebt: (file: string, code: number, ratio_pct: number, save = true) =>
    invoke<StockSummary>('set_debt', { file, code, ratio_pct, save }),
  setPrice: (file: string, code: number, yuan: number, field: 'init' | 'fact' = 'fact', save = true) =>
    invoke<StockSummary>('set_price', { file, code, yuan, field, save }),
  setRateLimit: (file: string, code: number, pct: number, save = true) =>
    invoke<StockSummary>('set_ratelimit', { file, code, pct, save }),
  saveFile: (file: string, force = true) => invoke<{ saved: string }>('save_file', { file, force }),

  // ---- extra（[extra] 社区贡献功能）----
  // [extra] 市场整顿
  rectify: (file: string, save = true) => invoke<{ summary: Record<string, string> }>('rectify', { file, save }),
  // [extra] 砍机构转散户
  npcToRetail: (file: string, save = true) => invoke<{ moved: Record<string, number> }>('npc_to_retail', { file, save }),
  // [extra] 退市
  delist: (file: string, code: number, to_b = false, save = true) =>
    invoke<{ mode: string }>('delist', { file, code, to_b, save }),
  // [extra] 分红
  dividend: (file: string, code: number, opts: { cash?: number; stock_gift?: number }, save = true) =>
    invoke<Record<string, unknown>>('dividend', { file, code, save, ...opts }),
  // [extra] 定向增发
  placement: (file: string, code: number, ratio = 0.8, amount = 1_000_000, save = true) =>
    invoke<{ new_shares: number; cost: number; issue_price: number }>('placement', { file, code, ratio, amount, save }),
};
