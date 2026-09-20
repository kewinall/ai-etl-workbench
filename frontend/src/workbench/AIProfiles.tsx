import {useEffect, useState, useCallback} from 'react';
import {request, jsonBody} from './api';

const roleFields = [
  ['requirement_gate', 'SA／需求確認模型'],
  ['etl_specification', 'Developer／規格設計模型'],
  ['qa_review', 'QA／證據審查模型'],
  ['file_understanding', '檔案理解模型（選用）'],
];

function ProfileEditor({profile, onSaved, onDirty}: {profile: any; onSaved: () => Promise<void>; onDirty: (id: string, dirty: boolean) => void}) {
  const [draft, setDraft] = useState(profile);
  const [secret, setSecret] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [testRole, setTestRole] = useState('requirement_gate');
  const [allowTest, setAllowTest] = useState(false);
  useEffect(() => {setDraft(profile)}, [profile]);
  const change = (key: string, value: any) => {setDraft({...draft, [key]: value}); setAllowTest(false)};
  const save = async () => {
    setBusy(true); setMessage('');
    let profileSaved = false;
    try {
      const {display_name, provider_type, endpoint, region, model_routes, enabled} = draft;
      await request(`/api/settings/ai-profiles/${profile.profile_id}`, jsonBody('PUT', {display_name, provider_type, endpoint: endpoint || null, region: region || null, model_routes, enabled}));
      profileSaved = true;
      if (secret) {
        await request(`/api/settings/ai-profiles/${profile.profile_id}/secret`, jsonBody('POST', {secret_value: secret}));
        setSecret('');
      }
      await onSaved();
      setAllowTest(false);
      setMessage('AI Profile 已儲存；尚未測試真實連線。');
    } catch (error: any) {setMessage(`${profileSaved ? 'Profile 已儲存，但機密或重新載入未完成：' : '儲存失敗：'}${error.message}`)}
    finally {setBusy(false)}
  };
  const test = async () => {
    setBusy(true); setMessage('');
    try {
      const result = await request(`/api/settings/ai-profiles/${profile.profile_id}/test?role=${testRole}`, {method: 'POST'});
      setMessage(`真實模型呼叫成功：${result.usage.model}，${result.usage.duration_ms} ms。僅驗證此角色的模型連線，不代表 ETL 通過。`);
    } catch (error: any) {setMessage(`模型測試未通過：${error.message}`)}
    finally {setBusy(false); setAllowTest(false)}
  };
  const dirty = JSON.stringify(draft) !== JSON.stringify(profile) || !!secret;
  useEffect(() => {onDirty(profile.profile_id,dirty); return () => onDirty(profile.profile_id,false)},[dirty,profile.profile_id,onDirty]);
  return <section className="panel setting-card ai-profile-card" aria-label={`AI Profile ${profile.profile_id}`}>
    <h3>{profile.display_name}</h3>
    <p>Profile ID：{profile.profile_id}。每個角色獨立指定模型，缺少路由會阻擋，不自動改用其他模型。</p>
    <fieldset className="settings-fields" disabled={busy} aria-label="AI Profile 編輯欄位" style={{border:0,padding:0,margin:0,minWidth:0}}>
      <label className="setting-field">顯示名稱<input value={draft.display_name || ''} onChange={e => change('display_name', e.target.value)}/></label>
      <label className="setting-field">AI 連線方式<select value={draft.provider_type} onChange={e => change('provider_type', e.target.value)}>
        <option value="LITELLM_BEDROCK">Amazon Bedrock（透過 LiteLLM SDK）</option>
        <option value="LITELLM_PROXY">LiteLLM Proxy</option>
        <option value="LOCAL_COPILOT">本機 GitHub Copilot CLI</option>
      </select></label>
      <label className="setting-field">AWS Region<input aria-label="AWS Region" value={draft.region || ''} onChange={e => change('region', e.target.value)}/><small>Bedrock 必填，須使用帳號有權限且模型可用的區域。</small></label>
      <label className="setting-field">LiteLLM Proxy Endpoint<input aria-label="LiteLLM Proxy Endpoint" value={draft.endpoint || ''} onChange={e => change('endpoint', e.target.value)}/><small>直接 Bedrock 請留白；Proxy 例如 http://gateway:4000/v1。</small></label>
      {roleFields.map(([role, label]) => <label className="setting-field" key={role}>{label}<input value={draft.model_routes?.[role] || ''} onChange={e => {
        const routes = {...draft.model_routes};
        if (e.target.value.trim()) routes[role] = e.target.value; else delete routes[role];
        change('model_routes', routes);
      }}/></label>)}
      {draft.provider_type === 'LOCAL_COPILOT' ? <p>使用 Windows 本機 Copilot 登入，不保存 Token；Region 與 Endpoint 請留白。角色模型必須指定明確名稱，不接受 auto。</p> : <label className="setting-field">更新 AI 機密<input aria-label="更新 AI 機密" type="password" autoComplete="new-password" value={secret} onChange={e => {setSecret(e.target.value); setAllowTest(false)}}/><small>{profile.secret_configured ? '已有機密，留白不變更。' : '尚無機密。'}Proxy 填 API key；Bedrock 填含 aws_access_key_id、aws_secret_access_key（可選 aws_session_token）的 JSON；未存機密時使用部署環境 AWS 身分。</small></label>}
      <label><input type="checkbox" checked={!!draft.enabled} onChange={e => change('enabled', e.target.checked)}/>啟用此 Profile</label>
    </fieldset>
    <div style={{display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 16}}>
      <button disabled={busy} onClick={() => {setDraft(profile); setSecret(''); setMessage(''); setAllowTest(false)}}>取消 AI 變更</button>
      <button className="primary" disabled={busy || !draft.display_name?.trim()} onClick={save}>儲存 AI Profile</button>
    </div>
    {draft.provider_type === 'LOCAL_COPILOT' ? <p>本機連線驗收請在 Task 通過需求檢查後授權一次 SA，並啟動 Windows 本機 Worker；容器內不會冒用 Windows 登入。</p> : <fieldset style={{marginTop: 20, padding: 12}}>
      <legend>真實模型連線測試</legend>
      <p>會送出簡短測試提示，可能產生用量費用；只測試已儲存的設定。</p>
      <label>測試角色<select disabled={busy} value={testRole} onChange={e => {setTestRole(e.target.value); setAllowTest(false)}}>{roleFields.map(([role, label]) => <option key={role} value={role}>{label}</option>)}</select></label>
      <label><input type="checkbox" checked={allowTest} disabled={dirty || busy} onChange={e => setAllowTest(e.target.checked)}/>我確認呼叫已儲存的模型並接受測試用量</label>
      <button disabled={busy || dirty || !allowTest} onClick={test}>執行模型連線測試</button>
    </fieldset>}
    {message && <p role="status">{message}</p>}
  </section>;
}

export function AIProfiles() {
  const [profiles, setProfiles] = useState<any[]>([]);
  const [error, setError] = useState('');
  const [dirtyIds,setDirtyIds] = useState<Set<string>>(new Set());
  const onDirty = useCallback((id: string, dirty: boolean) => setDirtyIds(old => {const next=new Set(old); if(dirty)next.add(id);else next.delete(id);return next}),[]);
  useEffect(() => {
    if(!dirtyIds.size)return;
    const beforeNavigate=(event: Event)=>{if(!event.defaultPrevented&&!window.confirm('AI Profile 有未儲存修改（包含尚未儲存的機密）。確定放棄並離開？'))event.preventDefault()};
    const beforeUnload=(event: BeforeUnloadEvent)=>{event.preventDefault();event.returnValue=''};
    window.addEventListener('workbench:before-navigate',beforeNavigate);
    window.addEventListener('beforeunload',beforeUnload);
    return ()=>{window.removeEventListener('workbench:before-navigate',beforeNavigate);window.removeEventListener('beforeunload',beforeUnload)};
  },[dirtyIds.size]);
  const load = async (savedId?: string) => {
    const items = await request<any[]>('/api/settings/ai-profiles');
    if (!savedId) {setProfiles(items); return}
    const saved = items.find(item => item.profile_id === savedId);
    if (!saved) throw new Error('已儲存的 Profile 無法重新讀取，請確認設定狀態。');
    // Preserve object identities of unrelated editors so their drafts survive.
    setProfiles(old => old.map(item => item.profile_id === savedId ? saved : item));
  };
  useEffect(() => {load().catch(error => setError(error.message))}, []);
  return <div><h2>AI 連線與角色模型</h2>{!!dirtyIds.size&&<p role="status">有 {dirtyIds.size} 個 AI Profile 尚未儲存</p>}{error && <p role="alert">{error}</p>}{profiles.map(profile => <ProfileEditor key={profile.profile_id} profile={profile} onSaved={() => load(profile.profile_id)} onDirty={onDirty}/>)}</div>;
}
