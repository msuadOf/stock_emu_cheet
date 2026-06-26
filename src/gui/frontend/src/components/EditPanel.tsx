import { useState } from 'react';
import { api, type StockSummary } from '../api';

interface Props {
  file: string;
  stock: StockSummary | null;
  onUpdated: (s: StockSummary) => void;
  setMessage: (m: string) => void;
}

// 主干编辑表单：PE / PB / 负债率 / 价格 / 涨跌停。输入显示值，提交调对应 backend 命令。
export function EditPanel({ file, stock, onUpdated, setMessage }: Props) {
  const [pe, setPe] = useState('');
  const [pb, setPb] = useState('');
  const [debt, setDebt] = useState('');
  const [price, setPrice] = useState('');
  const [rateLimit, setRateLimit] = useState('');

  if (!stock) return <div className="panel edit-panel"><em>请从左侧选择一只股票</em></div>;

  async function call(fn: () => Promise<StockSummary & { error?: string }>) {
    try {
      const r = await fn();
      if ((r as any).error) { setMessage('错误：' + (r as any).error); return; }
      onUpdated(r);
      setMessage('已更新');
    } catch (e) {
      setMessage('失败：' + String(e));
    }
  }

  return (
    <div className="panel edit-panel">
      <h3>编辑 — X{stock.code}</h3>
      <p className="hint">价格/股数均为游戏内部值；这里输入<b>显示值</b>（元 / 百分数），后端自动换算。</p>

      <div className="row">
        <label>目标 PE</label>
        <input value={pe} onChange={(e) => setPe(e.target.value)} placeholder="如 5.0" />
        <button onClick={() => call(() => api.setPe(file, stock.code, Number(pe)))}>设 PE</button>
      </div>

      <div className="row">
        <label>目标 PB</label>
        <input value={pb} onChange={(e) => setPb(e.target.value)} placeholder="如 0.5" />
        <button onClick={() => call(() => api.setPb(file, stock.code, Number(pb)))}>设 PB</button>
      </div>

      <div className="row">
        <label>目标负债率 %</label>
        <input value={debt} onChange={(e) => setDebt(e.target.value)} placeholder="如 30" />
        <button onClick={() => call(() => api.setDebt(file, stock.code, Number(debt)))}>设负债率</button>
      </div>

      <div className="row">
        <label>昨收价(元)</label>
        <input value={price} onChange={(e) => setPrice(e.target.value)} placeholder="如 12.50" />
        <button onClick={() => call(() => api.setPrice(file, stock.code, Number(price), 'fact'))}>设昨收</button>
      </div>

      <div className="row">
        <label>涨跌停 %</label>
        <input value={rateLimit} onChange={(e) => setRateLimit(e.target.value)} placeholder="如 10" />
        <button onClick={() => call(() => api.setRateLimit(file, stock.code, Number(rateLimit)))}>设涨跌停</button>
      </div>

      <dl className="summary">
        <dt>市值</dt><dd>{(stock.market_cap).toLocaleString()} 元</dd>
        <dt>总股本</dt><dd>{(stock.volume_total / 100).toLocaleString()} 股</dd>
        <dt>流通股</dt><dd>{(stock.volume_flow / 100).toLocaleString()} 股</dd>
        <dt>PE / PB</dt><dd>{stock.pe ?? 'N/A'} / {stock.pb ?? 'N/A'}</dd>
      </dl>
    </div>
  );
}
