import type { StockSummary } from '../api';

interface Props {
  stocks: StockSummary[];
  selectedCode: number | null;          // 单选（高亮）
  selectedCodes: number[];              // 多选（批量操作用）
  sectorFilter: number | string | '';  // 板块筛选（''=全部）
  sectors: (number | string)[];        // 存档内出现的板块列表
  onSelect: (code: number, e: React.MouseEvent) => void;   // 点行：单选；Shift 时区间多选
  onToggleMulti: (code: number) => void;
  onSelectAll: (all: boolean) => void;
  onSectorFilter: (s: number | string | '') => void;
  onSelectSector: () => void;           // 选中当前筛选板块的全部股票
}

export function StockList({ stocks, selectedCode, selectedCodes, sectorFilter, sectors, onSelect, onToggleMulti, onSelectAll, onSectorFilter, onSelectSector }: Props) {
  if (stocks.length === 0) {
    return <div className="panel stock-list"><em>无股票（先选存档并加载）</em></div>;
  }
  const shown = sectorFilter === '' ? stocks : stocks.filter((s) => s.sector === sectorFilter);
  const allChecked = shown.length > 0 && shown.every((s) => selectedCodes.includes(s.code));
  return (
    <div className="panel stock-list">
      <h3>股票列表 <span className="hint">（点行=选中；Shift+点行=区间多选）</span></h3>
      <div className="row" style={{ marginBottom: 6 }}>
        <label>板块筛选</label>
        <select value={sectorFilter} onChange={(e) => {
          const v = e.target.value;
          onSectorFilter(v === '' ? '' : (isNaN(Number(v)) ? v : Number(v)));
        }} title="按 Sector 筛选股票">
          <option value="">全部板块</option>
          {sectors.map((s) => <option key={String(s)} value={s}>板块 {s}</option>)}
        </select>
        <button onClick={onSelectSector} title="把当前筛选板块的所有股票加入多选">选该板块全部</button>
        <span className="hint">显示 {shown.length}/{stocks.length}</span>
      </div>
      <table>
        <thead>
          <tr>
            <th><input type="checkbox" checked={allChecked} onChange={(e) => {
              shown.forEach((s) => { if (e.target.checked !== selectedCodes.includes(s.code)) onToggleMulti(s.code); });
            }} title="全选/取消(当前筛选范围)" /></th>
            <th>代码</th><th>板块</th><th>昨收价</th><th>PE</th><th>PB</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((s) => {
            const checked = selectedCodes.includes(s.code);
            return (
              <tr
                key={s.code}
                className={s.code === selectedCode ? 'selected' : (checked ? 'multi-checked' : '')}
                onClick={(e) => onSelect(s.code, e)}
              >
                <td onClick={(e) => { e.stopPropagation(); onToggleMulti(s.code); }}>
                  <input type="checkbox" checked={checked} onChange={() => onToggleMulti(s.code)} />
                </td>
                <td>X{s.code}</td>
                <td>{s.sector ?? '-'}</td>
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
