import { useState } from 'react';
import { api, type StockSummary } from '../api';
import { ExtraBadge } from './ExtraBadge';

interface Props {
  file: string;
  stock: StockSummary | null;
  setMessage: (m: string) => void;
}

// [extra] 社区贡献功能面板：市场整顿 / 砍机构转散户 / 退市 / 分红 / 定向增发。
export function ExtraPanel({ file, stock, setMessage }: Props) {
  const [delistToB, setDelistToB] = useState(false);
  const [cash, setCash] = useState('');
  const [stockGift, setStockGift] = useState('');
  const [ratio, setRatio] = useState('0.8');
  const [amount, setAmount] = useState('1000000');

  async function run(fn: () => Promise<unknown>) {
    try {
      const r = await fn();
      setMessage('完成：' + JSON.stringify(r));
    } catch (e) {
      setMessage('失败：' + String(e));
    }
  }

  return (
    <div className="panel extra-panel">
      <h3>Extra 功能 <ExtraBadge /></h3>
      <p className="hint">社区贡献功能（公告/退市/增发/分红/市场整顿）。</p>

      <div className="extra-actions">
        <button onClick={() => run(() => api.rectify(file))}>市场整顿</button>
        <button onClick={() => run(() => api.npcToRetail(file))}>砍机构转散户</button>
      </div>

      <hr />
      <div className="row">
        <label>退市当前股</label>
        <label className="inline">
          <input type="checkbox" checked={delistToB} onChange={(e) => setDelistToB(e.target.checked)} />
          进 B 集合（完全退市）
        </label>
        <button
          disabled={!stock}
          onClick={() => run(() => api.delist(file, stock!.code, delistToB))}
        >
          退市
        </button>
      </div>

      <div className="row">
        <label>现金分红 每手(元)</label>
        <input value={cash} onChange={(e) => setCash(e.target.value)} placeholder="如 1.0" />
        <label className="inline">送股 10送</label>
        <input value={stockGift} onChange={(e) => setStockGift(e.target.value)} placeholder="如 3" />
        <button
          disabled={!stock}
          onClick={() => run(() => api.dividend(file, stock!.code, {
            cash: cash ? Number(cash) : undefined,
            stock_gift: stockGift ? Number(stockGift) : undefined,
          }))}
        >
          分红
        </button>
      </div>

      <div className="row">
        <label>定向增发 折价率</label>
        <input value={ratio} onChange={(e) => setRatio(e.target.value)} placeholder="0.8" />
        <label className="inline">支付(元)</label>
        <input value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="1000000" />
        <button
          disabled={!stock}
          onClick={() => run(() => api.placement(file, stock!.code, Number(ratio), Number(amount)))}
        >
          定向增发
        </button>
      </div>
    </div>
  );
}
