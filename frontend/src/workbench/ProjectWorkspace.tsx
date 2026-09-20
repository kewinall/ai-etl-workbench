import React, {useEffect, useState, useRef} from 'react';
import {request, jsonBody} from './api';
import './project-workspace.css';
import {ProjectDefaults} from './ProjectDefaults';
import {ProjectSummary} from './ProjectSummary';

type Project = {project_id: string; project_name: string; description: string; default_ai_profile: string; default_connection: string; naming_rules: Record<string, any>; updated_at: string};
type Props = {projectId?: string; tab?: string; navigate: (path: string) => void; onError: (message: string) => void};
const blank = () => ({project_name: '', description: '', default_ai_profile: 'nova-default', default_connection: 'vertica-default', naming_rules: {} as Record<string, any>});
const toForm = (p: Project) => ({project_name: p.project_name, description: p.description, default_ai_profile: p.default_ai_profile, default_connection: p.default_connection, naming_rules: structuredClone(p.naming_rules || {})});

export function ProjectWorkspace({projectId, tab = 'settings', navigate, onError}: Props) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [tasks, setTasks] = useState<any[]>([]);
  const [tasksLoading,setTasksLoading]=useState(false);
  const [tasksError,setTasksError]=useState('');
  const [tasksAttempt,setTasksAttempt]=useState(0);
  const [statusFilter,setStatusFilter]=useState('');
  const [form, setForm] = useState(blank);
  const [aliases, setAliases] = useState<[string, string][]>([]);
  const [snapshot, setSnapshot] = useState<Project | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [projectLoadError,setProjectLoadError]=useState('');
  const [projectLoadAttempt,setProjectLoadAttempt]=useState(0);
  const lastRequestedProject=useRef<string|undefined>(undefined);
  const [loadedProjectId, setLoadedProjectId] = useState<string | undefined>();
  const [message, setMessage] = useState('');
  const [query, setQuery] = useState('');
  const creating = projectId === 'new';
  const selected = projects.find(p => p.project_id === projectId);
  const dirty = !!projectId && !loading && tab !== 'history' && (
    JSON.stringify(form) !== JSON.stringify(snapshot ? toForm(snapshot) : blank()) ||
    JSON.stringify(aliases) !== JSON.stringify(Object.entries(snapshot?.naming_rules?.column_aliases || {})));
  const dirtyRef = useRef(dirty);
  dirtyRef.current = dirty;
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => {event.preventDefault(); event.returnValue = ''};
    const beforeNavigate = (event: Event) => {
      if (!dirtyRef.current) return;
      if (!window.confirm('專案設定尚未儲存。確定放棄修改並離開？')) event.preventDefault();
      else restore(snapshot || undefined);
    };
    window.addEventListener('beforeunload', warn);
    window.addEventListener('workbench:before-navigate', beforeNavigate);
    return () => {window.removeEventListener('beforeunload', warn); window.removeEventListener('workbench:before-navigate', beforeNavigate)};
  }, [dirty, snapshot]);
  const leave = navigate;
  const restore = (p?: Project) => {
    dirtyRef.current = false;
    setForm(p ? toForm(p) : blank());
    setAliases(Object.entries(p?.naming_rules?.column_aliases || {}));
    setSnapshot(p || null);
  };
  useEffect(() => {
    let active = true;
    setLoading(true);
    setProjectLoadError('');
    setLoadedProjectId(undefined);
    if (projectId === 'new' && lastRequestedProject.current !== 'new') restore();
    lastRequestedProject.current=projectId;
    request<Project[]>('/api/projects').then(items => {
      if (!active) return;
      setProjects(items);
      if (projectId && projectId !== 'new') restore(items.find(p => p.project_id === projectId));
      setLoadedProjectId(projectId);
      if (projectId && projectId !== 'new' && !items.some(p => p.project_id === projectId)) setMessage('找不到此專案，請從清單重新選擇。');
    }).catch(e => active && setProjectLoadError(e.message)).finally(() => active && setLoading(false));
    return () => {active = false};
  }, [projectId,projectLoadAttempt]);
  useEffect(() => {setMessage('')}, [projectId]);
  useEffect(() => {
    let active = true;
    setTasks([]);
    setTasksError('');
    setTasksLoading(false);
    if (projectId && !creating && tab === 'history') {
      setTasksLoading(true);
      request<any[]>(`/api/projects/${projectId}/tasks`).then(items => active && setTasks(items))
        .catch(e => active && setTasksError(e.message)).finally(()=>active&&setTasksLoading(false));
    }
    return () => {active = false};
  }, [projectId, tab, tasksAttempt]);
  useEffect(()=>{setQuery('');setStatusFilter('')},[projectId]);
  const visibleTasks=tasks.filter(t=>(!statusFilter||t.status===statusFilter)&&`${t.name} ${t.id}`.toLowerCase().includes(query.toLowerCase()));

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if(busy)return;
    setBusy(true); setMessage('');
    try {
      const dictionary: Record<string, string> = {};
      for (const [source, target] of aliases) {
        if (!source.trim() || !/^[a-z_][a-z0-9_]*$/.test(target.trim())) throw new Error('字典需填寫原始名稱，以及小寫英文 snake_case 名稱');
        if (source.trim() in dictionary) throw new Error('字典的原始名稱不可重複');
        dictionary[source.trim()] = target.trim();
      }
      const value = {...form, project_name: form.project_name.trim(), naming_rules: {...form.naming_rules, column_aliases: dictionary}, ...(!creating && snapshot ? {expected_updated_at: snapshot.updated_at} : {})};
      const result = await request<Project>(creating ? '/api/projects' : `/api/projects/${projectId}`, jsonBody(creating ? 'POST' : 'PUT', value));
      setProjects(old => [...old.filter(p => p.project_id !== result.project_id), result].sort((a,b) => a.project_name.localeCompare(b.project_name)));
      restore(result);
      navigate(`/projects/${result.project_id}/settings`);
      setMessage('已儲存；重新載入後仍可保留設定。');
    } catch (error: any) {setMessage(error.message)} finally {setBusy(false)}
  };

  if (!projectId) return <section className="panel wb-project-home" aria-label="專案工作區首頁">
    <div className="wb-heading"><div><h2>選擇工作專案</h2><p>設定、Task 與歷史紀錄都從專案開始。</p></div><button onClick={() => navigate('/projects/new/settings')}>新增專案</button></div>
    <label>搜尋專案<input value={query} onChange={event => setQuery(event.target.value)} placeholder="專案名稱或說明"/></label>
    {loading && <p role="status">正在讀取專案…</p>}
    {projectLoadError&&<div role="alert"><p>專案清單讀取失敗：{projectLoadError}</p><button onClick={()=>setProjectLoadAttempt(x=>x+1)}>重新讀取專案清單</button></div>}
    <div className="wb-project-home-list">{projects.filter(p => `${p.project_name} ${p.description}`.toLowerCase().includes(query.toLowerCase())).map(p => <article key={p.project_id}>
      <div><h3>{p.project_name}</h3><p>{p.description || '尚無說明'}</p><small>預設 AI：{p.default_ai_profile || '未設定'} · 連線：{p.default_connection || '未設定'}（非連線測試結果）</small></div>
      <button onClick={() => navigate(`/projects/${p.project_id}/settings`)} aria-label={`進入專案 ${p.project_name}`}>進入專案</button>
    </article>)}</div>
    {!loading && !projectLoadError && !projects.length && <p>尚無專案，請先建立第一個專案。</p>}
    {!loading && !!projects.length && !projects.some(p => `${p.project_name} ${p.description}`.toLowerCase().includes(query.toLowerCase())) && <p>沒有符合搜尋條件的專案。</p>}
  </section>;

  return <div className="wb-projects">
    <section className="wb-project-list panel" aria-label="專案清單">
      <div className="wb-heading"><h2>專案</h2><button disabled={busy} onClick={() => leave('/projects/new/settings')}>新增專案</button></div>
      {loading && <p role="status">讀取專案中…</p>}
      {projectLoadError&&<div role="alert"><p>專案清單讀取失敗：{projectLoadError}</p><button disabled={busy} onClick={()=>setProjectLoadAttempt(x=>x+1)}>重新讀取專案清單</button></div>}
      {projects.map(p => <button key={p.project_id} disabled={busy} aria-current={p.project_id === projectId ? 'page' : undefined} onClick={() => leave(`/projects/${p.project_id}/settings`)}><strong>{p.project_name}</strong><small>{p.description || '尚無說明'}</small></button>)}
      {!loading && !projectLoadError && !projects.length && <p>建立第一個專案以開始使用。</p>}
    </section>
    <section className="wb-project-content">
      <div className="panel wb-heading"><div><small>PROJECT WORKSPACE</small><h2>{creating ? '新增專案' : selected?.project_name || '選擇專案'}</h2></div>
        {!creating && selected && <button className="primary" disabled={busy} onClick={() => leave(`/projects/${projectId}/tasks/new`)}>建立 Task</button>}
      </div>
      {(creating || (selected && loadedProjectId === projectId && !loading)) && <>
        {!creating&&projectId&&<ProjectSummary key={projectId} projectId={projectId}/>}
        <div className="wb-tabs" role="tablist" aria-label="專案頁籤">
          <button role="tab" aria-selected={tab !== 'history'} disabled={busy} onClick={() => navigate(`/projects/${projectId}/settings`)}>設定</button>
          <button role="tab" aria-selected={tab === 'history'} disabled={creating || busy} onClick={() => leave(`/projects/${projectId}/history`)}>歷史 Task</button>
        </div>
        {tab !== 'history' ? <form className="panel wb-project-form" onSubmit={save}>
          <fieldset disabled={busy} aria-label="專案設定欄位" style={{border:0,padding:0,margin:0,minWidth:0}}>
          <h3>基本設定</h3>
          {dirty && <p role="status">有未儲存的專案設定</p>}
          <div className="wb-fields">
            <label>專案名稱<input required minLength={2} maxLength={120} value={form.project_name} onChange={e => setForm({...form, project_name: e.target.value})}/><small>2–120 字元，名稱不可重複。</small></label>
            <label>專案說明<textarea aria-label="專案說明" maxLength={4000} value={form.description} onChange={e => setForm({...form, description: e.target.value})}/></label>


          </div>
          <ProjectDefaults ai={form.default_ai_profile} connection={form.default_connection} change={(key, value) => setForm({...form, [key]: value})}/>
          <h3>專案命名字典</h3><p>優先使用此專案的中英對照建議；欄位仍需在 Task 中確認。</p>
          {aliases.map(([source,target], index) => <div className="wb-alias" key={index}>
            <input aria-label={`原始名稱 ${index+1}`} placeholder="例如：客戶編號" value={source} onChange={e => setAliases(old => old.map((row,i) => i === index ? [e.target.value,row[1]] : row))}/>
            <input aria-label={`英文名稱 ${index+1}`} placeholder="customer_id" value={target} onChange={e => setAliases(old => old.map((row,i) => i === index ? [row[0],e.target.value] : row))}/>
            <button type="button" aria-label={`移除對照 ${index+1}`} onClick={() => setAliases(old => old.filter((_,i) => i !== index))}>移除</button>
          </div>)}
          <button type="button" onClick={() => setAliases(old => [...old, ['', '']])}>新增對照</button>
          <div className="wb-actions"><button type="button" disabled={busy} onClick={() => {restore(selected); if (creating) navigate(projects.length ? `/projects/${projects[0].project_id}/settings` : '/projects')}}>取消變更</button><button className="primary" type="submit" disabled={busy || form.project_name.trim().length < 2}>{busy ? '儲存中…' : creating ? '建立專案' : '儲存設定'}</button></div>
          </fieldset>
        </form> : <section className="panel wb-history" aria-label="專案歷史 Task">
          <p>以下為歷史 Task 狀態，不代表最新 Run 已通過 QA 或可交付；請進入 Task 查看版本與證據。</p>
          <label>搜尋 Task<input value={query} onChange={e => setQuery(e.target.value)} placeholder="名稱或 Task ID"/></label>
          <label>篩選 Task 狀態<select aria-label="篩選 Task 狀態" value={statusFilter} onChange={e=>setStatusFilter(e.target.value)} disabled={tasksLoading||!!tasksError}><option value="">全部狀態</option>{Array.from(new Set(tasks.map(t=>String(t.status)))).sort().map(status=><option key={status} value={status}>{status}（{tasks.filter(t=>t.status===status).length}）</option>)}</select></label>
          {tasksLoading?<p role="status">正在讀取歷史 Task…</p>:tasksError?<div role="alert"><p>歷史 Task 讀取失敗：{tasksError}</p><button onClick={()=>setTasksAttempt(attempt=>attempt+1)}>重新讀取歷史 Task</button></div>:<>
            <p role="status">顯示 {visibleTasks.length} / {tasks.length} 個 Task</p>
            {visibleTasks.map(t => <button className="wb-history-row" key={t.id} onClick={() => navigate(`/projects/${projectId}/tasks/${encodeURIComponent(t.id)}`)}><span><strong>{t.name}</strong><small>{t.id} · {t.source} → {t.target}</small></span><span>{t.status} →</span></button>)}
            {!tasks.length?<p>此專案尚無 Task，可使用上方「建立 Task」。</p>:!visibleTasks.length&&<p>沒有符合搜尋或狀態條件的 Task。</p>}
          </>}
        </section>}
      </>}
      {message && <div className="panel wb-message" role="status">{message}</div>}
    </section>
  </div>;
}
