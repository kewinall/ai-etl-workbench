import {useEffect, useState} from 'react';
import {request} from './api';

export function ProjectDefaults({ai, connection, change}: {ai: string; connection: string; change: (key: string, value: string) => void}) {
  const [profiles, setProfiles] = useState<any[]>([]);
  const [settings, setSettings] = useState<any>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const load = async () => {
    setLoading(true); setError('');
    try {const [p, s] = await Promise.all([request('/api/settings/ai-profiles'), request('/api/settings/groups')]); setProfiles(p); setSettings(s.values)}
    catch (error: any) {setError(error.message)} finally {setLoading(false)}
  };
  useEffect(() => {load()}, []);
  const qa = settings?.data_connections_targets?.etl_qa;
  const connectionId = typeof qa === 'object' ? qa?.connection_id : null;
  const platformAI = settings?.ai_provider_model_strategy?.default_profile;
  return <fieldset className="wb-defaults"><legend>專案執行預設</legend>
    <p>Task 明確指定 → 本專案 → 平台預設。設定改變不覆寫歷史快照，待處理版本需重新確認。</p>
    {error && <p role="alert">選項讀取失敗：{error}。目前保存值未被更改。</p>}
    <div className="wb-fields">
      <label>預設 AI Profile<select aria-label="預設 AI Profile" disabled={loading} value={ai} onChange={e => change('default_ai_profile', e.target.value)}>
        <option value="">沿用平台預設</option>
        {ai && !profiles.some(p => p.profile_id === ai) && <option value={ai}>{ai}（目前無法確認）</option>}
        {profiles.map(p => <option key={p.profile_id} value={p.profile_id} disabled={!p.enabled}>{p.display_name} · {p.profile_id}{p.enabled ? '' : '（已停用）'}</option>)}
      </select><small>{ai ? '來源：本專案指定' : `來源：平台預設 · ${platformAI || '尚未設定'}`}</small></label>
      <label>預設資料連線<select aria-label="預設資料連線" disabled={loading} value={connection} onChange={e => change('default_connection', e.target.value)}>
        <option value="">沿用平台預設</option>
        {connection && connection !== connectionId && <option value={connection}>{connection}（尚無有效設定）</option>}
        {connectionId && <option value={connectionId}>{qa.display_name || connectionId} · Vertica ETL／QA</option>}
      </select><small>{connection ? '來源：本專案指定' : `來源：平台預設 · ${connectionId || '尚未配置有效連線'}`}</small></label>
    </div>
    <p>可選擇不代表連線測試通過。平台 PostgreSQL 不提供為 ETL 目標。</p>
    <button type="button" disabled={loading} onClick={load}>重新載入設定選項</button> <a href="#/system">前往平台設定中心</a>
  </fieldset>;
}
