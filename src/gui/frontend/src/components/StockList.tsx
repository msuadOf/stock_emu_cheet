import type { StockSummary } from '../api';

interface Props {
  stocks: StockSummary[];
  selectedCode: number | null;          // 单选（高亮）
  selectedCodes: number[];              // 多选（批量操作用）
  onSelect: (code: number) => void;     // 单选
  onToggleMulti: (code: number) => void;
  onSelectAll: (all: boolean) => void;
}

export function StockList({ stocks, selectedCode, selectedCodes, onSelect, onToggleMulti, onSelectAll }: Props) {
  if (stocks.length === 0) {
    return <div className="panel stock-list"><em>无股票（先选存档并加载）</em></div>;
  }
  const allChecked = selectedCodes.length === stocks.length && stocks.length > 0;
  return (
    <div className="panel stock-list">
      <h3>股票列表 <span className="hint">（勾选多个→批量；点行→单股编辑）</span></h3>
      <table>
        <thead>
          <tr>
            <th><input type="checkbox" checked={allChecked} onChange={(e) => onSelectAll(e.target.checked)} title="全选/取消" /></th>
            <th>代码</th><th>昨收价</th><th>PE</th><th>PB</th>
          </tr>
        </thead>
        <tbody>
          {stocks.map((s) => {
            const checked = selectedCodes.includes(s.code);
            return (
              <tr
                key={s.code}
                className={s.code === selectedCode ? 'selected' : (checked ? 'multi-checked' : '')}
                onClick={() => onSelect(s.code)}
              >
                <td onClick={(e) => { e.stopPropagation(); onToggleMulti(s.code); }}>
                  <input type="checkbox" checked={checked} onChange={() => onToggleMulti(s.code)} />
                </td>
                <td>X{s.code}</td>
                <td>{(s.price_fact / 100).toFixed(2)}</td>
                <td>{s.pe ?? 'N/A'}</td>
                <td>{s.pb ?? 'N/A'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
