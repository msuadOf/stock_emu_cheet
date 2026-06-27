import { useState } from 'react';
import { api, type StockSummary } from './api';
import { SaveBar } from './components/SaveBar';
import { StockList } from './components/StockList';
import { EditPanel } from './components/EditPanel';

export default function App() {
  const [file, setFile] = useState('');
  const [stocks, setStocks] = useState<StockSummary[]>([]);
  const [selectedCode, setSelectedCode] = useState<number | null>(null);  // 单选
  const [selectedCodes, setSelectedCodes] = useState<number[]>([]);        // 多选（批量）
  const [message, setMessage] = useState('');

  const selected = stocks.find((s) => s.code === selectedCode) ?? null;

  function toggleMulti(code: number) {
    setSelectedCodes((prev) => prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]);
  }
  function selectAll(all: boolean) {
    setSelectedCodes(all ? stocks.map((s) => s.code) : []);
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
          onSelect={setSelectedCode}
          onToggleMulti={toggleMulti}
          onSelectAll={selectAll}
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
