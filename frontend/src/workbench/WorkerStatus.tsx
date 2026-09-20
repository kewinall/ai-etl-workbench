import {useEffect, useState} from 'react';
import {request} from './api';

const names: Record<string, string> = {
  CONTROL: '需求檢查 Worker', SA_LITELLM: 'Bedrock／Proxy SA Worker', SA_COPILOT: 'Windows Copilot Worker',
};

export function WorkerStatus({kind}: {kind?: string}) {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const next = await request('/api/runtime/workers');
        if (active) {setData(next); setError('')}
      } catch {if (active) setError('無法確認 Worker 狀態；不要將舊心跳當成目前在線。')}
    };
    load();
    const timer = window.setInterval(load, 10000);
    return () => {active = false; window.clearInterval(timer)};
  }, []);
  const refresh = async () => {
    setBusy(true);
    try {setData(await request('/api/runtime/workers')); setError('')}
    catch {setError('無法確認 Worker 狀態；請檢查平台資料庫。')}
    finally {setBusy(false)}
  };
  return <section className="worker-status" aria-label={kind ? `${names[kind]}存活狀態` : 'Worker 存活狀態'}>
    <h4>{kind ? '負責此模型的 Worker' : '執行服務狀態'}</h4>
    <p>依資料庫最近 45 秒心跳判斷，每 10 秒更新。在線不代表模型連線、Hop 或 Vertica 已驗收。</p>
    <button disabled={busy} onClick={refresh}>更新 Worker 狀態</button>
    {error ? <p role="alert">{error}</p> : !data ? <p>正在確認 Worker…</p> : <ul>
      {data.workers.filter((worker: any) => !kind || worker.kind === kind).map((worker: any) => <li key={worker.kind}>
        <strong>{names[worker.kind] || worker.kind}</strong>
        <span>：{worker.status === 'ONLINE' ? worker.can_dispatch ? '近期有心跳・派發模式' : '近期有心跳・僅觀察，不派發' : worker.status === 'OFFLINE' ? '離線或已停止' : '尚未收到心跳'}</span>
        <small>最近心跳：{worker.last_seen ? new Date(worker.last_seen).toLocaleString() : '尚無紀錄'}</small>
      </li>)}
    </ul>}
  </section>;
}
