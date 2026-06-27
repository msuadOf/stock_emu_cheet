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
  const [batchTarget, setBatchTarget] = useState('inst');
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

  // ===================== 批量模式 =====================
  if (isBatch) {
    const n = selectedCodes.length;
    return (
      <div className="panel edit-panel">
        <h3>批量操作（已选 {n} 只）</h3>
        <p className="hint">对所选 {n} 只股票统一执行下列操作之一。</p>

        <fieldset>
          <legend>批量持仓</legend>
          <div className="row">
            <label>持仓 = 流通股 ×</label>
            <input value={batchPct} onChange={(e) => setBatchPct(e.target.value)} placeholder="如 10（表示10%）" />
            <label className="inline">%</label>
            <select value={batchTarget} onChange={(e) => setBatchTarget(e.target.value)} title="筹码守恒过户对象">
              <option value="inst">从主力扣/补</option>
              <option value="ret">从散户扣/补</option>
              <option value="hot">从游资扣/补</option>
            </select>
            <button onClick={() => run(() => api.batchPlayerPct(file, selectedCodes, Number(batchPct), batchTarget),
              `已批量持仓 ${n} 只（流通股×${batchPct}%，带筹码守恒）`)}>设持仓</button>
          </div>
          <p className="hint">注：筹码不足会触发增发（守恒优先，实际持仓可能≠精确比例）。</p>
        </fieldset>

        <fieldset>
          <legend>批量 NPC 挂单</legend>
          <div className="row">
            <label className="inline"><input type="checkbox" checked={batchApplyInst} onChange={(e) => setBatchApplyInst(e.target.checked)} />主力</label>
            <label className="inline"><input type="checkbox" checked={batchApplyRet} onChange={(e) => setBatchApplyRet(e.target.checked)} />散户</label>
          </div>
          <div className="row">
            <label>愿意购入资金</label>
            <input value={batchAmountBuy} onChange={(e) => setBatchAmountBuy(e.target.value)} placeholder="AmountBuy（留空不改）" />
            <span className="hint">调高=容易涨；0=无人买</span>
          </div>
          <div className="row">
            <label>卖压(可卖股数)</label>
            <input value={batchVolSell} onChange={(e) => setBatchVolSell(e.target.value)} placeholder="VolSell（留空不改）" />
            <span className="hint">调高=卖压大涨不动；0=卖不动</span>
          </div>
          <button onClick={() => run(() => api.batchNpcQuotes(file, selectedCodes, {
            amount_buy: batchAmountBuy ? Number(batchAmountBuy) : null,
            volume_sell: batchVolSell ? Number(batchVolSell) : null,
            apply_inst: batchApplyInst, apply_ret: batchApplyRet,
          }), `已批量改 NPC 挂单（${n} 只）`)}>改挂单</button>
        </fieldset>

        <fieldset>
          <legend>批量 NPC 购买取向 <ExtraBadge /></legend>
          <p className="hint">改 NoticeStyle 个股级参数（全局生效，作用于所有股票的 NPC 行为）。</p>
          <div className="row">
            <label>买入力度 Strength</label>
            <input value={batchStrength} onChange={(e) => setBatchStrength(e.target.value)} placeholder="如 2.0=翻倍, 0.5=减半" />
          </div>
          <div className="row">
            <label>建仓概率 Prob</label>
            <input value={batchProb} onChange={(e) => setBatchProb(e.target.value)} placeholder="0~1，如 0.5" />
          </div>
          <button onClick={() => run(() => api.batchNoticeStyle(file, selectedCodes, {
            strength: batchStrength ? Number(batchStrength) : null,
            create_prob: batchProb ? Number(batchProb) : null,
          }), `已改 NPC 购买取向（力度/概率）`)}>改取向</button>
        </fieldset>
      </div>
    );
  }

  // ===================== 单股模式 =====================
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
    </div>
  );
}
