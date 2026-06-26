import { useRef } from 'react';
import { api } from '../api';

interface Props {
  file: string;
  onFileChange: (f: string) => void;
  onStocksLoaded: (stocks: { stocks: import('../api').StockSummary[]; count: number }) => void;
  message: string;
  setMessage: (m: string) => void;
}

export function SaveBar({ file, onFileChange, onStocksLoaded, message, setMessage }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  async function load() {
    if (!file) return;
    try {
      const res = await api.listStocks(file);
      onStocksLoaded(res);
      setMessage(`已加载 ${res.count} 只股票`);
    } catch (e) {
      setMessage('加载失败：' + String(e));
    }
  }

  async function save() {
    if (!file) return;
    try {
      const r = await api.saveFile(file, true);
      setMessage('已保存：' + r.saved);
    } catch (e) {
      setMessage('保存失败：' + String(e));
    }
  }

  return (
    <div className="save-bar">
      <input
        ref={inputRef}
        type="text"
        placeholder="存档文件路径 (.sav)"
        value={file}
        onChange={(e) => onFileChange(e.target.value)}
        style={{ flex: 1 }}
      />
      <button onClick={load} disabled={!file}>加载列表</button>
      <button onClick={save} disabled={!file}>保存</button>
      <span className="msg">{message}</span>
    </div>
  );
}
