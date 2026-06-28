import { useState, useRef } from 'react';
import { api, type StockSummary } from './api';
import { SaveBar } from './components/SaveBar';
import { StockList } from './components/StockList';
import { EditPanel } from './components/EditPanel';

export default function App() {
  const [file, setFile] = useState('');
  const [stocks, setStocks] = useState<StockSummary[]>([]);
  const [selectedCode, setSelectedCode] = useState<number | null>(null);  // 单选
  const [selectedCodes, setSelectedCodes] = useState<number[]>([]);        // 多选（批量）
  const [sectorFilter, setSectorFilter] = useState<number | string>('');
  const [message, setMessage] = useState('');
  const lastClickCode = useRef<number | null>(null);   // Shift 区间多选的起点

  const selected = stocks.find((s) => s.code === selectedCode) ?? null;
  // 存档内出现的所有板块（去重、排序）
  const sectors = Array.from(new Set(stocks.map((s) => s.sector).filter((x) => x !== undefined && x !== null))) as (number | string)[];

  function toggleMulti(code: number) {
    setSelectedCodes((prev) => prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]);
    lastClickCode.current = code;
  }
  function selectAll(all: boolean) {
    setSelectedCodes(all ? stocks.map((s) => s.code) : []);
  }

  // 点行：普通点击=单选高亮；Shift 点击=从上次点击到当前点区间多选（正序逆序均可）
  function handleSelect(code: number, e: React.MouseEvent) {
    if (e.shiftKey && lastClickCode.current !== null) {
      const codes = stocks.map((s) => s.code);
      const a = codes.indexOf(lastClickCode.current);
      const b = codes.indexOf(code);
      if (a !== -1 && b !== -1) {
        const [lo, hi] = a < b ? [a, b] : [b, a];
        const range = codes.slice(lo, hi + 1);
        setSelectedCodes((prev) => Array.from(new Set([...prev, ...range])));
        setSelectedCode(code);
        return;
      }
    }
    setSelectedCode(code);
    lastClickCode.current = code;
  }

  // 任何编辑/批量操作后，重新拉股票列表刷新右侧摘要
  async function refresh() {
    if (!file) return;
    try {
      const res = await api.listStocks(file);
      setStocks(res.stocks);
    } catch { /* setMessage 由调用方处理 */ }
  }

  return (
    <div className="app">
      <SaveBar
        file={file}
        onFileChange={setFile}
        onStocksLoaded={(res) => { setStocks(res.stocks); setSelectedCode(null); setSelectedCodes([]); }}
        message={message}
        setMessage={setMessage}
      />
      <div className="main">
        <StockList
          stocks={stocks}
          selectedCode={selectedCode}
          selectedCodes={selectedCodes}
          sectorFilter={sectorFilter}
          sectors={sectors}
          onSelect={handleSelect}
          onToggleMulti={toggleMulti}
          onSelectAll={selectAll}
          onSectorFilter={setSectorFilter}
          onSelectSector={() => {
            if (sectorFilter === '') return;
            const inSector = stocks.filter((s) => s.sector === sectorFilter).map((s) => s.code);
            setSelectedCodes((prev) => Array.from(new Set([...prev, ...inSector])));
          }}
        />
        <EditPanel
          file={file}
          stock={selected}
          selectedCodes={selectedCodes}
          onUpdated={refresh}
          setMessage={setMessage}
        />
      </div>
    </div>
  );
}
