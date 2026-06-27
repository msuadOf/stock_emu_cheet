import { useEffect, useState } from 'react';
import { open } from '@tauri-apps/plugin-dialog';
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

// 顶部存档选择栏：
//   [扫描目录输入框]（默认填 core 的默认目录，可手动改成任意目录） [刷新槽]
//   -> 选存档槽 -> 选 .sav 文件 -> 加载/保存
export function SaveBar({ file, onFileChange, onStocksLoaded, message, setMessage }: Props) {
  const [dir, setDir] = useState('');          // 当前扫描目录（可编辑，初始=默认目录）
  const [slots, setSlots] = useState<Slot[]>([]);
  const [slotPath, setSlotPath] = useState('');
  const [files, setFiles] = useState<SaveFile[]>([]);

  // 按某目录刷新存档槽列表
  async function refreshSlots(base: string) {
    onFileChange('');
    setSlotPath('');
    setFiles([]);
    if (!base.trim()) { setSlots([]); return; }
    try {
      const r = await api.listSlots(base.trim());
      setSlots(r.slots);
      setMessage(`扫描 ${base.trim()}：${r.slots.length} 个存档槽`);
    } catch (e) {
      setSlots([]);
      setMessage('列槽失败: ' + String(e));
    }
  }

  // 启动时：取默认目录，填入输入框并刷新槽
  useEffect(() => {
    (async () => {
      try {
        const r = await api.getDefaultSave();
        setDir(r.default_dir);
        await refreshSlots(r.default_dir);
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

  // 弹原生目录选择对话框，选完后填入并刷新槽
  async function browseDir() {
    try {
      const selected = await open({ directory: true, multiple: false, defaultPath: dir || undefined });
      if (typeof selected === 'string' && selected) {
        setDir(selected);
        await refreshSlots(selected);
      }
    } catch (e) {
      setMessage('选择目录失败: ' + String(e));
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
      <input
        type="text"
        value={dir}
        onChange={(e) => setDir(e.target.value)}
        placeholder="存档目录（默认已填，可手动修改）"
        title="扫描目录：默认填游戏存档目录，可改成任意路径"
        style={{ flex: 2, minWidth: 260 }}
      />
      <button onClick={browseDir} title="弹出系统目录选择对话框">浏览…</button>
      <button onClick={() => refreshSlots(dir)} title="按上面的目录刷新存档槽">刷新槽</button>
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
      <span className="msg">{message}</span>
    </div>
  );
}
