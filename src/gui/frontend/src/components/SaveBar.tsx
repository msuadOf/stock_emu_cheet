import { useEffect, useState } from 'react';
import { api } from '../api';

interface Props {
  file: string;
  onFileChange: (f: string) => void;
  onStocksLoaded: (stocks: { stocks: import('../api').StockSummary[]; count: number }) => void;
  message: string;
  setMessage: (m: string) => void;
}

interface Slot { name: string; path: string; file_count: number; }
interface SaveFile { name: string; path: string; size_kb: number; modified: string; }

// 顶部存档选择栏：默认目录 -> 选存档槽 -> 选 .sav 文件 -> 加载/保存。
// 默认目录由后端 get_default_save 命令返回（core 的 default_save_dir），不写死在前端。
export function SaveBar({ file, onFileChange, onStocksLoaded, message, setMessage }: Props) {
  const [defaultDir, setDefaultDir] = useState('');
  const [slots, setSlots] = useState<Slot[]>([]);
  const [slotPath, setSlotPath] = useState('');
  const [files, setFiles] = useState<SaveFile[]>([]);

  // 启动时：取默认目录 + 列槽
  useEffect(() => {
    (async () => {
      try {
        const r = await api.getDefaultSave();
        setDefaultDir(r.default_dir);
        const s = await api.listSlots(r.default_dir);
        setSlots(s.slots);
        setMessage(`默认目录: ${r.default_dir}`);
      } catch (e) {
        setMessage('获取默认目录失败: ' + String(e));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 选了槽 -> 列文件
  async function onSlotChange(path: string) {
    setSlotPath(path);
    onFileChange('');
    if (!path) { setFiles([]); return; }
    try {
      const r = await api.listFiles(path);
      setFiles(r.files);
    } catch (e) {
      setMessage('列文件失败: ' + String(e));
    }
  }

  async function load() {
    if (!file) return;
    try {
      const res = await api.listStocks(file);
      onStocksLoaded(res);
      setMessage(`已加载 ${res.count} 只股票`);
    } catch (e) {
      setMessage('加载失败: ' + String(e));
    }
  }

  async function save() {
    if (!file) return;
    try {
      const r = await api.saveFile(file, true);
      setMessage('已保存: ' + r.saved);
    } catch (e) {
      setMessage('保存失败: ' + String(e));
    }
  }

  return (
    <div className="save-bar">
      <select value={slotPath} onChange={(e) => onSlotChange(e.target.value)} title="选择存档槽">
        <option value="">— 存档槽 —</option>
        {slots.map((s) => (
          <option key={s.path} value={s.path}>{s.name} ({s.file_count})</option>
        ))}
      </select>
      <select value={file} onChange={(e) => onFileChange(e.target.value)} title="选择 .sav 文件">
        <option value="">— .sav 文件 —</option>
        {files.map((f) => (
          <option key={f.path} value={f.path}>{f.name} ({f.size_kb} KB, {f.modified})</option>
        ))}
      </select>
      <button onClick={load} disabled={!file}>加载</button>
      <button onClick={save} disabled={!file}>保存</button>
      <span className="msg" title={defaultDir}>{message}</span>
    </div>
  );
}
