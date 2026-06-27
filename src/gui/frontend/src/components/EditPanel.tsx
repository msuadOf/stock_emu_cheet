import { useState } from 'react';
import { api, type StockSummary } from '../api';
import { ExtraBadge } from './ExtraBadge';

interface Props {
  file: string;
  stock: StockSummary | null;           // 单股（selectedCode 对应）
  selectedCodes: number[];              // 多选（批量）
  onUpdated: () => void;                // 任何改动后，让父组件重新拉列表
  setMessage: (m: string) => void;
}

/* 统一编辑面板：根据多选/单股切换。
 * - 多选(>=2) → 批量操作区（持仓% / NPC挂单 / NoticeStyle）
 * - 单选/未选 → 单股编辑（PE/PB/价格...）+ extra 功能（退市/分红/增发，标 extra badge）
 * extra 功能不再单列一栏，与普通功能合并在同一面板，仅用 badge 标注。
 */
export function EditPanel({ file, stock, selectedCodes, onUpdated, setMessage }: Props) {
  // 单股编辑用的本地输入
  const [pe, setPe] = useState(''); const [pb, setPb] = useState('');
  const [debt, setDebt] = useState(''); const [price, setPrice] = useState('');
  const [rateLimit, setRateLimit] = useState('');
  // extra（单股）
  const [delistToB, setDelistToB] = useState(false);
  const [cash, setCash] = useState(''); const [stockGift, setStockGift] = useState('');
  const [ratio, setRatio] = useState('0.8'); const [amount, setAmount] = useState('1000000');
  // 批量
  const [batchPct, setBatchPct] = useState('10');
  const [batchStrategy, setBatchStrategy] = useState('inst');
  const [batchAmountBuy, setBatchAmountBuy] = useState('');
  const [batchVolSell, setBatchVolSell] = useState('');
  const [batchApplyInst, setBatchApplyInst] = useState(true);
  const [batchApplyRet, setBatchApplyRet] = useState(true);
  const [batchStrength, setBatchStrength] = useState('');
  const [batchProb, setBatchProb] = useState('');

  const isBatch = selectedCodes.length >= 2;

  async function run(fn: () => Promise<unknown>, okMsg?: string) {
    try {
      const r = await fn();
      setMessage(okMsg ?? ('完成：' + JSON.stringify(r)));
      await onUpdated();
    } catch (e) {
      setMessage('失败：' + String(e));
    }
  }

  // 批量操作区（持仓 / NPC挂单 / 取向）。单股时也显示——作用于当前选中的股票。
  // codes：单股且未多选时，作用于当前这只；否则作用于 selectedCodes。
  const batchCodes = selectedCodes.length > 0 ? selectedCodes : (stock ? [stock.code] : []);
  const batchPanel = (
    <fieldset className="batch-block">
      <legend>批量操作（作用于已选 {batchCodes.length} 只）</legend>
      <div className="row">
        <label>持仓 = 流通股 ×</label>
        <input value={batchPct} onChange={(e) => setBatchPct(e.target.value)} placeholder="如 10（表示10%）" />
        <label className="inline">%</label>
        <select value={batchStrategy} onChange={(e) => setBatchStrategy(e.target.value)} title="筹码守恒扣仓位策略">
          <option value="inst">优先主力扣/补</option>
          <option value="ret">优先散户扣/补</option>
          <option value="hot">优先游资扣/补</option>
          <option value="balance_ir">主力+散户 按比例均衡</option>
          <option value="ret_then_inst">先散户后机构(游资兜底)</option>
          <option value="npc_proportional">5类NPC 按比例均匀扣</option>
        </select>
        <button onClick={() => run(() => api.batchPlayerPct(file, batchCodes, Number(batchPct), batchStrategy),
          `已批量持仓 ${batchCodes.length} 只（流通股×${batchPct}%，策略 ${batchStrategy}）`)}>设持仓</button>
      </div>
      <p className="hint">筹码守恒：持仓变化按所选策略从对应账户可卖里扣减/回补，总流通股不变、不增发。</p>

      <div className="row">
        <label className="inline"><input type="checkbox" checked={batchApplyInst} onChange={(e) => setBatchApplyInst(e.target.checked)} />主力</label>
        <label className="inline"><input type="checkbox" checked={batchApplyRet} onChange={(e) => setBatchApplyRet(e.target.checked)} />散户</label>
        <label>挂单 资金/卖压</label>
        <input value={batchAmountBuy} onChange={(e) => setBatchAmountBuy(e.target.value)} placeholder="AmountBuy" />
        <input value={batchVolSell} onChange={(e) => setBatchVolSell(e.target.value)} placeholder="VolSell" />
        <button onClick={() => run(() => api.batchNpcQuotes(file, batchCodes, {
          amount_buy: batchAmountBuy ? Number(batchAmountBuy) : null,
          volume_sell: batchVolSell ? Number(batchVolSell) : null,
          apply_inst: batchApplyInst, apply_ret: batchApplyRet,
        }), `已批量改 NPC 挂单（${batchCodes.length} 只）`)}>改挂单</button>
      </div>

      <div className="row">
        <label>购买取向 力度/概率 <ExtraBadge /></label>
        <input value={batchStrength} onChange={(e) => setBatchStrength(e.target.value)} placeholder="Strength" />
        <input value={batchProb} onChange={(e) => setBatchProb(e.target.value)} placeholder="Prob" />
        <button onClick={() => run(() => api.batchNoticeStyle(file, batchCodes, {
          strength: batchStrength ? Number(batchStrength) : null,
          create_prob: batchProb ? Number(batchProb) : null,
        }), `已改 NPC 购买取向（${batchCodes.length} 只）`)}>改取向</button>
      </div>
    </fieldset>
  );

  // ===================== 多选专属视图 =====================
  if (isBatch) {
    return (
      <div className="panel edit-panel">
        <h3>批量操作（已选 {selectedCodes.length} 只）</h3>
        <p className="hint">对所选 {selectedCodes.length} 只股票统一执行下列操作。</p>
        {batchPanel}
      </div>
    );
  }

  // ===================== 单股模式（单股表单 + 批量区都显示） =====================
  if (!stock) {
    return <div className="panel edit-panel"><em>从左侧选一只股票编辑，或勾选多只做批量操作。</em></div>;
  }

  async function callSingle(fn: () => Promise<StockSummary & { error?: string }>) {
    try {
      const r = await fn();
      if ((r as any).error) { setMessage('错误：' + (r as any).error); return; }
      setMessage('已更新');
      await onUpdated();
    } catch (e) {
      setMessage('失败：' + String(e));
    }
  }

  return (
    <div className="panel edit-panel">
      <h3>编辑 — X{stock.code}</h3>
      <p className="hint">价格输入<b>显示值</b>（元 / 百分数），后端自动换算内部值。</p>

      <fieldset>
        <legend>估值</legend>
        <div className="row"><label>目标 PE</label><input value={pe} onChange={(e) => setPe(e.target.value)} placeholder="如 5.0" /><button onClick={() => callSingle(() => api.setPe(file, stock.code, Number(pe)))}>设 PE</button></div>
        <div className="row"><label>目标 PB</label><input value={pb} onChange={(e) => setPb(e.target.value)} placeholder="如 0.5" /><button onClick={() => callSingle(() => api.setPb(file, stock.code, Number(pb)))}>设 PB</button></div>
        <div className="row"><label>负债率 %</label><input value={debt} onChange={(e) => setDebt(e.target.value)} placeholder="如 30" /><button onClick={() => callSingle(() => api.setDebt(file, stock.code, Number(debt)))}>设负债率</button></div>
      </fieldset>

      <fieldset>
        <legend>价格 / 涨跌停</legend>
        <div className="row"><label>昨收价(元)</label><input value={price} onChange={(e) => setPrice(e.target.value)} placeholder="如 12.50" /><button onClick={() => callSingle(() => api.setPrice(file, stock.code, Number(price), 'fact'))}>设昨收</button></div>
        <div className="row"><label>涨跌停 %</label><input value={rateLimit} onChange={(e) => setRateLimit(e.target.value)} placeholder="如 10" /><button onClick={() => callSingle(() => api.setRateLimit(file, stock.code, Number(rateLimit)))}>设涨跌停</button></div>
      </fieldset>

      <fieldset>
        <legend>公司行动 <ExtraBadge /></legend>
        <div className="row">
          <label>退市</label>
          <label className="inline"><input type="checkbox" checked={delistToB} onChange={(e) => setDelistToB(e.target.checked)} />进 B 集合(完全退市)</label>
          <button onClick={() => run(() => api.delist(file, stock.code, delistToB))}>退市</button>
        </div>
        <div className="row">
          <label>分红</label>
          <input value={cash} onChange={(e) => setCash(e.target.value)} placeholder="现金每手元" />
          <label className="inline">送股10送</label>
          <input value={stockGift} onChange={(e) => setStockGift(e.target.value)} placeholder="如 3" />
          <button onClick={() => run(() => api.dividend(file, stock.code, { cash: cash ? Number(cash) : undefined, stock_gift: stockGift ? Number(stockGift) : undefined }))}>分红</button>
        </div>
        <div className="row">
          <label>定向增发</label>
          <input value={ratio} onChange={(e) => setRatio(e.target.value)} placeholder="折价率0.8" />
          <input value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="支付元" />
          <button onClick={() => run(() => api.placement(file, stock.code, Number(ratio), Number(amount)))}>增发</button>
        </div>
      </fieldset>

      <dl className="summary">
        <dt>市值</dt><dd>{(stock.market_cap).toLocaleString()} 元</dd>
        <dt>总/流通股</dt><dd>{(stock.volume_total / 100).toLocaleString()} / {(stock.volume_flow / 100).toLocaleString()}</dd>
        <dt>PE / PB</dt><dd>{stock.pe ?? 'N/A'} / {stock.pb ?? 'N/A'}</dd>
      </dl>

      {batchPanel}
    </div>
  );
}
