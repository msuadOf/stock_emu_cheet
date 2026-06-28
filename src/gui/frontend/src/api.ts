// pyInvoke 封装层：与 src/gui/backend/commands.py 的 @commands.command() 一一对应。
// 通过官方 JS 绑定 `tauri-plugin-pytauri-api` 调用后端命令。
// 注意：必须 import 这个包，不能直接用 window.__TAURI__.pytauri（那样会 undefined 导致白屏）。

import { pyInvoke } from 'tauri-plugin-pytauri-api';

export interface StockSummary {
  code: number;
  bourse?: number | string;
  sector?: number | string;
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

  // ---- 批量操作 ----
  // strategy 即扣仓位策略：inst/ret/hot(顺序扣)、balance_ir(主力+散户按比例均衡)、
  // ret_then_inst(先散户后机构,游资兜底)、npc_proportional(5类NPC按比例均匀扣)。
  // codes/sector 二选一：给 sector 时作用于该板块全部股票。
  batchPlayerPct: (file: string, args: { codes?: number[]; sector?: number | string; pct: number; strategy?: string }, save = true) =>
    invoke<{ results: Record<string, { volume: number; action: string }>; count: number }>('batch_player_pct', { file, save, ...args }),
  batchNpcQuotes: (file: string, args: { codes?: number[]; sector?: number | string; amount_buy?: number | null; volume_sell?: number | null; apply_inst?: boolean; apply_ret?: boolean }, save = true) =>
    invoke<{ results: Record<string, unknown>; count: number }>('batch_npc_quotes', { file, save, ...args }),
  batchNoticeStyle: (file: string, args: { codes?: number[]; sector?: number | string; strength?: number | null; create_prob?: number | null }, save = true) =>
    invoke<{ applied: number; strength?: number | null; create_prob?: number | null }>('batch_notice_style', { file, save, ...args }),
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
  // 单股自由设定全部财务字段（防回滚）
  setFinancials: (file: string, code: number, fields: Record<string, number>, save = true) =>
    invoke<StockSummary>('set_financials', { file, code, fields, save }),
  // 单股 NPC 挂单：median|1.5x|0.5x|clear|custom
  setNpcQuotes: (file: string, code: number, mode: string, opts?: { vus?: number; aub?: number; rvus?: number; raub?: number }, save = true) =>
    invoke<StockSummary>('set_npc_quotes', { file, code, mode, save, ...(opts || {}) }),
  // 玩家持仓 增/改/删 + 总资金
  playerPos: (file: string, mode: 'add' | 'modify' | 'delete', code: number, amount?: number, volume?: number, save = true) =>
    invoke<Record<string, unknown>>('player_pos', { file, mode, code, amount, volume, save }),
  playerAmount: (file: string, amount: number, save = true) =>
    invoke<{ amount_raw: number }>('player_amount', { file, amount, save }),
  // 存档瘦身三件套
  cleanNoticeGroup: (file: string, save = true) => invoke<{ before: number; form: string }>('clean_notice_group', { file, save }),
  cleanTradeType: (file: string, save = true) => invoke<{ before: number }>('clean_trade_type', { file, save }),
  trimHuddleNpc: (file: string, keep: number, save = true) => invoke<{ before: number; after: number; accounts: number }>('trim_huddle_npc', { file, keep, save }),
  // NPC 购买取向预设 1-5
  setNoticeStyle: (file: string, mode: number, save = true) => invoke<{ applied: boolean; mode: number }>('set_notice_style', { file, mode, save }),
  // 详情 / 板块
  stockDetail: (file: string, code: number) => invoke<Record<string, unknown> & { error?: string }>('stock_detail', { file, code }),
  listSectors: (file: string) => invoke<{ sectors: { sector: number | string; count: number }[] }>('list_sectors', { file }),
  stocksBySector: (file: string, sector: number | string) => invoke<{ stocks: StockSummary[]; count: number }>('stocks_by_sector', { file, sector }),
  // [extra] 公告：发布 + 查看 + 删除
  publishNotice: (file: string, args: { code: number; notice_day: number; star: number; kind: 'notice' | 'report'; strength?: number; create_prob?: number; report_strength?: number; is_buy?: boolean; asset_net?: number; asset_loan?: number; reward_business?: number; reward_other?: number; cost_business?: number; cost_other?: number }, save = true) =>
    invoke<Record<string, unknown>>('publish_notice', { file, save, ...args }),
  listNotices: (file: string, code: number) => invoke<{ normal: unknown[]; reports: unknown[] }>('list_notices', { file, code }),
  deleteNotice: (file: string, code: number, kind: 'normal' | 'report', index: number, save = true) =>
    invoke<{ deleted?: boolean; remaining?: number; error?: string }>('delete_notice', { file, code, kind, index, save }),
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
