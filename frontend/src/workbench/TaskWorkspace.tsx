import {useEffect, useRef, useState, type ReactNode} from 'react';
import {request} from './api';
import {ExecutionReadiness} from './ExecutionReadiness';
import {RunVersions} from './RunVersions';
import {OracleHistory} from './OracleHistory';
import {SdmDelivery} from './SdmDelivery';

const tabs = [['overview','概覽'],['requirements','需求與規格'],['collaboration','協作紀錄'],['artifacts','產物與流程'],['execution','執行與 QA'],['delivery','交付']] as const;
type Tab = typeof tabs[number][0];
const time = (value: string) => value ? new Date(value).toLocaleString() : '未記錄';
const stateLabels: Record<string, string> = {QUEUED: '等待輸入確認／領取', RUNNING: '處理中', NEEDS_REVIEW: '需要人工檢查', SUCCEEDED: '流程結束（不等於交付核准）', FAILED: '失敗', CANCELLED: '已取消'};
const eventLabels: Record<string, string> = {ENQUEUED: '保存準備版本', INPUT_APPROVE: '人工確認輸入', INPUT_REJECT: '人工拒絕輸入', CLAIMED: '控制程式領取', REQUIREMENT_GATE_STARTED: '開始需求檢查', PIPELINE_NOT_READY: '初步檢查完成，後續流程尚未接通', REQUIREMENT_NEEDS_INPUT: '需求缺漏，等待補正', SA_QUEUED: '人工授權 SA 並排隊', SA_DISPATCH_RESERVED: '保存 SA 派發意圖', SA_VALIDATED_NOT_APPROVED: 'SA 結構驗證通過，等待人工核准', OPERATOR_CANCELLED: '人工取消版本'};

function Collaboration({taskId}: {taskId: string}) {
  const [runs, setRuns] = useState<any[]>([]);
  const [selected, setSelected] = useState('');
  const [detail, setDetail] = useState<any>(null);
  const [invocation, setInvocation] = useState<any>(null);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [listPending, setListPending] = useState(true);
  useEffect(() => {
    let live = true;
    setListPending(true);
    request(`/api/tasks/${taskId}/runs`).then(data => {if (live) {setRuns(data.runs); setSelected(old => old || data.runs[0]?.run_id || '')}}).catch(e => live && setError(e.message)).finally(() => live && setListPending(false));
    return () => {live = false};
  }, [taskId, refresh]);
  useEffect(() => {
    let live = true;
    setDetail(null); setInvocation(null); setError('');
    if (selected) Promise.all([request(`/api/tasks/${taskId}/runs/${selected}`), request(`/api/tasks/${taskId}/runs/${selected}/sa-invocation`)])
      .then(([run, sa]) => {if (live) {setDetail(run); setInvocation(sa.invocation)}}).catch(e => live && setError(e.message));
    return () => {live = false};
  }, [taskId, selected, refresh]);
  return <section className="panel" aria-label="版本協作紀錄">
    <h3>版本協作紀錄</h3><p>依保存紀錄顯示人工決定、控制程式與 SA 模型。Developer／QA 角色交接尚未接通，不以固定節點冒充 AI。</p>
    <button onClick={() => setRefresh(n => n + 1)}>重新整理協作紀錄</button>
    {error && <p role="alert">無法讀取紀錄：{error}</p>}
    {listPending && <p role="status">正在讀取版本清單…</p>}
    {!runs.length && !error && !listPending && <p>尚無版本協作紀錄；舊節點與 Log 請至「產物與流程」及「執行與 QA」。</p>}
    {!!runs.length && <label>查看協作版本<select value={selected} onChange={e => setSelected(e.target.value)}>{runs.map(run => <option key={run.run_id} value={run.run_id}>{time(run.created_at)} · {stateLabels[run.state] || run.state} · {run.run_id}</option>)}</select></label>}
    {detail && <>
      <p>Run：{detail.run_id} · 輸入 checksum：{detail.input_checksum}</p>
      <p>{detail.matches_current ? '符合目前輸入與設定。' : '歷史版本，不能沿用為目前核准。'}</p>
      {detail.approval && <article className="wb-record"><b>人工操作 · 輸入確認</b><p>{detail.approval.decision}；不等於 Hop 執行或 Release 核准。</p></article>}
      <h4>控制程式事件（依保存順序）</h4>
      {detail.events?.length ? <ol className="wb-timeline">{detail.events.map((event: any) => <li key={event.event_id}>
        <b>{event.event_type === 'SDM_CANDIDATE_SAVED' ? '程式工具保存 SDM 候選文件（非 Release）' : event.event_type === 'SPECIFICATION_SAVED' ? '程式驗證後保存規格' : event.event_type === 'SPECIFICATION_APPROVED' ? '人工核准規格（非執行授權）' : eventLabels[event.event_type] || '控制流程事件'}</b>
        <small>{time(event.created_at)} · {event.event_type} · {event.phase}</small>
        {event.event_type === 'SDM_CANDIDATE_SAVED' ? <p>候選文件：{event.event_context.sdm_id}<br/>規格 checksum：{event.event_context.specification_checksum}<br/>文件 checksum：{event.event_context.checksum}</p> : event.event_context?.specification_id && <p>規格第 {event.event_context.version} 版 · {event.event_context.specification_id}<br/>內容 checksum：{event.event_context.checksum}</p>}
        {event.event_context?.approval_id && <p>核准紀錄：{event.event_context.approval_id}。這是當時的操作紀錄；目前是否有效，請至「需求與規格」重新檢查。</p>}
      </li>)}</ol> : <p>此版本尚無控制事件。</p>}
      <h4>AI 角色：SA</h4>
      {invocation ? <article className="wb-record"><p>{invocation.model} · {invocation.status}</p><p>此紀錄不等於需求已核准。模型輸出、引用及用量可在「需求與規格」選擇同一版本查閱。</p></article> : <p>此版本尚無 SA 呼叫紀錄。</p>}
    </>}
  </section>;
}

export function TaskWorkspace({task, tab, navigate, renderSetup, renderValue}: {task: any; tab?: string; navigate: (path: string) => void; renderSetup: (task: any) => ReactNode; renderValue: (value: any) => ReactNode}) {
  const current: Tab = tabs.some(([key]) => key === tab) ? tab as Tab : 'overview';
  const [detail, setDetail] = useState(task);
  const [assets, setAssets] = useState<any>(null);
  const [runs, setRuns] = useState<any[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [nodeKey, setNodeKey] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [visitedRequirements, setVisitedRequirements] = useState(current === 'requirements');
  const [deliveryRun, setDeliveryRun] = useState('');
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const base = `/projects/${encodeURIComponent(task.project_id)}/tasks/${encodeURIComponent(task.id)}`;
  const select = (key: Tab) => {if (key === 'requirements') setVisitedRequirements(true); navigate(`${base}/${key}`)};
  useEffect(() => {if (current === 'requirements') setVisitedRequirements(true)}, [current]);
  useEffect(() => {
    let live = true;
    setBusy(true); setError('');
    Promise.all([request(`/api/tasks/${task.id}`), request(`/api/tasks/${task.id}/history-assets`), request(`/api/tasks/${task.id}/runs`)])
      .then(([d, a, r]) => {if (live) {setDetail(d); setAssets(a); setRuns(r.runs)}})
      .catch(e => {if (live) {setAssets(null); setRuns([]); setError(e.message)}})
      .finally(() => live && setBusy(false));
    return () => {live = false};
  }, [task.id, refresh, current]);
  const nodes = detail.nodes || [];
  const node = nodes.find((item: any) => item.key === nodeKey);
  const jobs = assets?.jobs || [];
  const latest = runs[0];
  const nodeDetail = node && <section className="panel node-pretty" aria-label="節點詳細資訊"><h3>{node.label} 詳細資訊</h3><button onClick={() => setNodeKey('')}>關閉節點詳情</button><p>節點代碼：{node.key} · {node.status} · {node.duration_ms == null ? '尚無耗時' : `${Math.round(node.duration_ms)} ms`}</p><h4>輸入與輸出結果</h4>{renderValue(node.detail || {})}<h4>相關事件</h4>{(detail.logs || []).filter((log: any) => log.node === node.key).map((log: any, i: number) => <article key={i}><p>{time(log.time)} · {log.level} · {log.message}</p>{renderValue(log.detail || {})}</article>)}</section>;
  return <div className="wb-task-workspace">
    <div className="wb-task-heading"><div><small>{detail.id}</small><h2>{detail.name}</h2><p>專案內 Task · {detail.source} → {detail.target}</p></div><button disabled={busy} onClick={() => setRefresh(n => n + 1)}>{busy ? '讀取中…' : '重新整理 Task'}</button></div>
    <div role="tablist" aria-label="Task 工作區" className="wb-task-tabs">{tabs.map(([key, label], i) => <button ref={el => {tabRefs.current[i] = el}} key={key} id={`task-tab-${key}`} role="tab" aria-selected={current === key} aria-controls={`task-panel-${key}`} tabIndex={current === key ? 0 : -1} onClick={() => select(key)} onKeyDown={e => {
      let index: number;
      if (e.key === 'ArrowRight') index = (i + 1) % tabs.length;
      else if (e.key === 'ArrowLeft') index = (i + tabs.length - 1) % tabs.length;
      else if (e.key === 'Home') index = 0;
      else if (e.key === 'End') index = tabs.length - 1;
      else return;
      e.preventDefault(); select(tabs[index][0]); tabRefs.current[index]?.focus();
    }}>{label}</button>)}</div>
    {error && <p role="alert">無法重新讀取完整 Task 資料：{error}。以下既有內容可能不是最新狀態，請重新整理。</p>}
    {tabs.map(([key]) => <section role="tabpanel" id={`task-panel-${key}`} aria-labelledby={`task-tab-${key}`} hidden={current !== key} key={key}>
      {key === 'overview' && <>
        <section className="panel"><h3>目前狀態與下一步</h3>{latest ? <><p>最新準備版本：{latest.state} · {latest.phase || '階段未記錄'}</p><p>結果／阻擋代碼：{latest.outcome_code || '尚無結果'}</p><p>Run：{latest.run_id}</p></> : <p>{busy ? '正在讀取版本…' : error ? '無法確認最新版本。' : '尚無準備版本。'}</p>}<p>既有 Task 狀態：{detail.status}；不代表目前版本已取得執行或交付核准。</p><button onClick={() => select('requirements')}>前往需求確認與補正</button></section>
        <ExecutionReadiness taskId={task.id}/>
      </>}
      {key === 'requirements' && (visitedRequirements || current === key) && <>
        <RunVersions key={task.id} taskId={task.id}/><section className="panel"><h3>建立 Task 的完整設定</h3><p>下方是目前 Task 保存內容；歷次不可變快照請查看上方版本。</p>{renderSetup(detail)}</section>
      </>}
      {key === 'collaboration' && current === key && <Collaboration taskId={task.id}/>}
      {key === 'artifacts' && <>
        <section className="panel"><h3>節點狀態</h3><p>保留既有節點紀錄；節點名稱不代表本次曾呼叫 AI。新版編譯流程尚未接通。</p>{nodes.map((n: any, i: number) => <button className="node nodebutton" key={n.key} aria-pressed={nodeKey === n.key} onClick={() => setNodeKey(n.key)}><span>{i + 1}</span><div><b>{n.label}</b><small>{n.status}</small></div></button>)}</section>{nodeDetail}
        <section className="panel"><h3>Hop Job 與流程</h3>{!assets ? <p>產物清單尚未讀取成功。</p> : !jobs.length ? <p>尚未產生 Hop Job。</p> : jobs.map((job: any) => <article className="wb-record" key={job.artifact_id}><h4>{job.name}</h4><p>v{job.version} · {job.artifact_type} · 舊版產物（尚未綁定新版交付核准）</p><div className="hpl-canvas">{(job.transforms || []).map((t: any, i: number) => <div className="hpl-transform" key={i}><b>{t.name}</b><small>{t.type}</small></div>)}</div><ul>{(job.hops || []).map((h: any, i: number) => <li key={i}>{h.from} → {h.to}</li>)}</ul><details><summary>XML／完整定義</summary><pre>{job.content}</pre></details></article>)}</section>
        <section className="panel"><h3>所有 SQL</h3>{assets?.sql?.length ? assets.sql.map((sql: any, i: number) => <article key={i}><h4>{sql.artifact} · {sql.node}</h4><pre>{sql.sql}</pre></article>) : <p>{assets ? '目前 Job 沒有內嵌 SQL。' : 'SQL 清單尚未讀取成功。'}</p>}</section>
      </>}
      {key === 'execution' && <>
        {current === 'execution' && <OracleHistory taskId={task.id}/>}
        <section className="panel"><h3>舊版 Task 執行紀錄</h3><p>舊版進度 {detail.progress}% · 寫入筆數 {detail.rows ?? '未記錄'} · 節點 {detail.current_step || '未記錄'}</p><p>以下保留舊版執行資料，不代表上方選取 Run 的結果。新版 Hop、結果比對與 QA 狀態請以上方版本證據為準；舊版的 0% 或零筆不會覆蓋新版結果。</p>{detail.last_error && renderValue(detail.last_error)}{detail.error_test_result && renderValue(detail.error_test_result)}</section>
        <section className="panel terminal"><h3>執行 Log</h3>{detail.logs?.length ? detail.logs.map((log: any, i: number) => <article key={i}><code>{time(log.time)} · {log.level} · {log.node} — {log.message}</code>{Object.keys(log.detail || {}).length > 0 && renderValue(log.detail)}</article>) : <p>尚無執行紀錄。</p>}</section>
        <section className="panel terminal"><h3>舊版 Apache Hop Log</h3>{assets?.hop_logs?.length ? assets.hop_logs.map((log: any, i: number) => <article key={i}><b>{log.log_type}</b><pre>{log.log_content}</pre></article>) : <p>{assets ? '舊版紀錄沒有 Hop log；這不表示新版 Run 沒有執行日誌，請查看上方 QA 的 Hop 執行證據。' : '舊版 Hop Log 尚未讀取成功。'}</p>}</section>
      </>}
      {key === 'delivery' && <>
        <section className="panel"><h3>版本交付</h3><p>選擇版本後查看 SDM、可攜驗證與正式交付狀態。只有通過完整 QA、可攜驗證及人工交付核准的版本，才提供正式 Release ZIP。</p>
          {busy?<p role="status">正在確認版本清單…</p>:error?<p>版本清單讀取失敗，請重新整理 Task。</p>:runs.length?<>
            <label>選擇 SDM 準備版本<select value={runs.some(run=>run.run_id===deliveryRun)?deliveryRun:runs[0].run_id} onChange={event=>setDeliveryRun(event.target.value)}>{runs.map(run=><option key={run.run_id} value={run.run_id}>{time(run.created_at)} · {run.run_id}</option>)}</select></label>
            {current==='delivery'&&<SdmDelivery key={runs.some(run=>run.run_id===deliveryRun)?deliveryRun:runs[0].run_id} base={`/api/tasks/${encodeURIComponent(task.id)}/runs/${encodeURIComponent(runs.some(run=>run.run_id===deliveryRun)?deliveryRun:runs[0].run_id)}`}/>}
          </>:<p>尚無準備版本。請先到需求與規格建立版本並確認規格。</p>}
        </section>
        <section className="panel downloads"><h3>既有成果下載</h3><p>保留舊 Task 成功產物的查閱與下載，不等於 RELEASE_READY，不應視為可直接交付客戶的 ZIP。</p>{detail.status === 'SUCCEEDED' && jobs.length ? jobs.map((job: any) => <a className="download-card" key={job.artifact_id} href={job.download_url}><div><b>{job.name}</b><small>{job.artifact_type} v{job.version} · {Number(job.file_size).toLocaleString()} bytes</small></div><span>下載</span></a>) : <p>{!assets ? '下載清單尚未讀取成功。' : 'Task 尚未成功或尚無既有成果。'}</p>}</section>
      </>}
    </section>)}
  </div>;
}
