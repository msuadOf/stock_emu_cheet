import type { StockSummary } from '../api';

interface Props {
  stocks: StockSummary[];
  selectedCode: number | null;
  onSelect: (code: number) => void;
}

export function StockList({ stocks, selectedCode, onSelect }: Props) {
  if (stocks.length === 0) {
    return <div className="panel stock-list"><em>无股票（先点「加载列表」）</em></div>;
  }
  return (
    <div className="panel stock-list">
      <h3>股票列表</h3>
      <table>
        <thead>
          <tr><th>代码</th><th>昨收价</th><th>PE</th><th>PB</th></tr>
        </thead>
        <tbody>
          {stocks.map((s) => (
            <tr
              key={s.code}
              className={s.code === selectedCode ? 'selected' : ''}
              onClick={() => onSelect(s.code)}
            >
              <td>X{s.code}</td>
              <td>{(s.price_fact / 100).toFixed(2)}</td>
              <td>{s.pe ?? 'N/A'}</td>
              <td>{s.pb ?? 'N/A'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
