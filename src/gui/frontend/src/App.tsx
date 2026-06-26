import { useState } from 'react';
import { type StockSummary } from './api';
import { SaveBar } from './components/SaveBar';
import { StockList } from './components/StockList';
import { EditPanel } from './components/EditPanel';
import { ExtraPanel } from './components/ExtraPanel';

export default function App() {
  const [file, setFile] = useState('');
  const [stocks, setStocks] = useState<StockSummary[]>([]);
  const [selectedCode, setSelectedCode] = useState<number | null>(null);
  const [message, setMessage] = useState('');

  const selected = stocks.find((s) => s.code === selectedCode) ?? null;

  function handleUpdated(updated: StockSummary) {
    setStocks((prev) => prev.map((s) => (s.code === updated.code ? updated : s)));
  }

  return (
    <div className="app">
      <SaveBar
        file={file}
        onFileChange={setFile}
        onStocksLoaded={(res) => { setStocks(res.stocks); setSelectedCode(null); }}
        message={message}
        setMessage={setMessage}
      />
      <div className="main">
        <StockList stocks={stocks} selectedCode={selectedCode} onSelect={setSelectedCode} />
        <EditPanel file={file} stock={selected} onUpdated={handleUpdated} setMessage={setMessage} />
        <ExtraPanel file={file} stock={selected} setMessage={setMessage} />
      </div>
    </div>
  );
}
