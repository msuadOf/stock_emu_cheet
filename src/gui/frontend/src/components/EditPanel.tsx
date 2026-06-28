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
        <input value={batchPct} onChange={(e) => setBatchPct(e.target.value)} placeholder="如 10" title="百分数 0~100。如填 10 = 把玩家持仓设为该股流通股的 10%" />
        <label className="inline">%</label>
        <select value={batchStrategy} onChange={(e) => setBatchStrategy(e.target.value)} title="筹码守恒扣仓位策略：玩家持仓从对应账户可卖里扣/补">
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
      <p className="hint">
        把玩家对所选股票的持仓统一设为「流通股 × 百分数」。筹码守恒（从对应账户可卖扣/补，不增发，不足记 shortfall）。策略：
        <b>优先主力/散户/游资</b>＝按该账户顺序依次扣；<b>按比例均衡</b>＝主力+散户按各自可卖占比分摊；
        <b>先散户后机构</b>＝先散户、再机构、游资兜底；<b>5类NPC按比例</b>＝遍历 5 类 NPC 按可卖比例扣（不碰主力/散户/游资）。
      </p>

      <div className="row">
        <label className="inline" title="勾选才改对应账户"><input type="checkbox" checked={batchApplyInst} onChange={(e) => setBatchApplyInst(e.target.checked)} />主力</label>
        <label className="inline"><input type="checkbox" checked={batchApplyRet} onChange={(e) => setBatchApplyRet(e.target.checked)} />散户</label>
        <label>资金/卖压</label>
        <input value={batchAmountBuy} onChange={(e) => setBatchAmountBuy(e.target.value)} placeholder="资金" title="AmountUsableBuy 内部值。调高=买盘强易涨；0=无人买。留空不改" />
        <input value={batchVolSell} onChange={(e) => setBatchVolSell(e.target.value)} placeholder="卖压" title="VolumeUsableSell 内部值。调高=卖压大涨不动；0=卖不动。留空不改" />
        <button onClick={() => run(() => api.batchNpcQuotes(file, batchCodes, {
          amount_buy: batchAmountBuy ? Number(batchAmountBuy) : null,
          volume_sell: batchVolSell ? Number(batchVolSell) : null,
          apply_inst: batchApplyInst, apply_ret: batchApplyRet,
        }), `已批量改 NPC 挂单（${batchCodes.length} 只）`)}>改挂单</button>
      </div>
      <p className="hint">改主力/散户五档买卖盘的「可买资金」与「可卖股数」（内部值，约=显示值的 100 倍）。两项可只填一个，留空的不改。</p>

      <div className="row">
        <label>力度/概率 <ExtraBadge /></label>
        <input value={batchStrength} onChange={(e) => setBatchStrength(e.target.value)} placeholder="力度" title="NormalStockStrength。1.0=默认，2.0=力度翻倍，0.5=减半。留空不改" />
        <input value={batchProb} onChange={(e) => setBatchProb(e.target.value)} placeholder="概率" title="NormalStockCreateProb。0~1 小数，如 0.5=50%主动建仓。留空不改" />
        <button onClick={() => run(() => api.batchNoticeStyle(file, batchCodes, {
          strength: batchStrength ? Number(batchStrength) : null,
          create_prob: batchProb ? Number(batchProb) : null,
        }), `已改 NPC 购买取向（${batchCodes.length} 只）`)}>改取向</button>
      </div>
      <p className="hint">改全局 NPC 行为：力度（买卖强度倍率，1.0=正常）、建仓概率（0~1）。作用于所有股票的 NPC。</p>
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
        <div className="row"><label>目标 PE</label><input value={pe} onChange={(e) => setPe(e.target.value)} placeholder="如 5.0" title="市盈率 = 股价×股本/净利润。设目标 PE 会反推净利润并清零成本。0.1=极低估，1=正常，10=偏高，负=亏损" /><button onClick={() => callSingle(() => api.setPe(file, stock.code, Number(pe)))}>设 PE</button></div>
        <div className="row"><label>目标 PB</label><input value={pb} onChange={(e) => setPb(e.target.value)} placeholder="如 0.5" title="市净率 = 股价×股本/净资产。设目标 PB 会反推净资产。0.1=远低于净资产，1=正常，10=偏高" /><button onClick={() => callSingle(() => api.setPb(file, stock.code, Number(pb)))}>设 PB</button></div>
        <div className="row"><label>负债率 %</label><input value={debt} onChange={(e) => setDebt(e.target.value)} placeholder="如 30" title="资产负债率百分数 1~99。如 30 表示 30%。会反推总负债" /><button onClick={() => callSingle(() => api.setDebt(file, stock.code, Number(debt)))}>设负债率</button></div>
        <p className="hint">设目标估值，自动反推对应的财务字段（净利润/净资产/总负债）。输入显示值，越低越「便宜」。</p>
      </fieldset>

      <fieldset>
        <legend>价格 / 涨跌停</legend>
        <div className="row"><label>昨收价(元)</label><input value={price} onChange={(e) => setPrice(e.target.value)} placeholder="如 12.50" title="PriceFact 显示价（元）。今日开盘基准，并强制同步最后一根 K 线的 OHLC" /><button onClick={() => callSingle(() => api.setPrice(file, stock.code, Number(price), 'fact'))}>设昨收</button></div>
        <div className="row"><label>涨跌停 %</label><input value={rateLimit} onChange={(e) => setRateLimit(e.target.value)} placeholder="如 10" title="RateLimit 百分数。5=小波动，10=默认，20=大幅波动" /><button onClick={() => callSingle(() => api.setRateLimit(file, stock.code, Number(rateLimit)))}>设涨跌停</button></div>
        <p className="hint">输入<b>显示值</b>（元 / 百分数），后端自动换算内部值。改昨收会同步 K 线让游戏内最新价立刻变。</p>
      </fieldset>

      <fieldset>
        <legend>公司行动 <ExtraBadge /></legend>
        <div className="row">
          <label>退市</label>
          <label className="inline" title="不勾=进 A 集合（警告退市，限涨跌 5%）；勾上=进 B 集合（完全退市，删股票池+玩家持仓，不可恢复）"><input type="checkbox" checked={delistToB} onChange={(e) => setDelistToB(e.target.checked)} />进 B 集合(完全退市)</label>
          <button onClick={() => run(() => api.delist(file, stock.code, delistToB))}>退市</button>
        </div>
        <div className="row">
          <label>分红</label>
          <input value={cash} onChange={(e) => setCash(e.target.value)} placeholder="现金" title="每手现金分红（元/100股），如 2.0 = 每100股派2元。受净资产/负债率上限约束，超限拒。留空=只送股" />
          <label className="inline">送股10送</label>
          <input value={stockGift} onChange={(e) => setStockGift(e.target.value)} placeholder="如 3" title="送股比例 X（10送X），如 3 = 每10股送3股。按比例放大持仓、股价等比降、总市值不变。留空=只现金" />
          <button onClick={() => run(() => api.dividend(file, stock.code, { cash: cash ? Number(cash) : undefined, stock_gift: stockGift ? Number(stockGift) : undefined }))}>分红</button>
        </div>
        <div className="row">
          <label>定向增发</label>
          <input value={ratio} onChange={(e) => setRatio(e.target.value)} placeholder="折价率" title="发行价 = 近20日均价 × 折价率。0.8=八折（常见），0.7=七折，1.0=不折价" />
          <input value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="支付元" title="玩家认购金额（元）。新增股数 = 金额/发行价，加入流通股、扣玩家资金" />
          <button onClick={() => run(() => api.placement(file, stock.code, Number(ratio), Number(amount)))}>增发</button>
        </div>
        <p className="hint">公司行动（Extra）。退市按净资产/负债筛选；分红可现金+送股组合；增发按均价折价发行。</p>
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
