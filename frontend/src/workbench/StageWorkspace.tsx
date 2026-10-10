import {useCallback, useEffect, useRef, useState, type ReactNode} from 'react';
import {request} from './api';
import {RunVersions} from './RunVersions';
import {SAEvidence} from './SAEvidence';
import {SAInvocation} from './SAInvocation';
import {NamingConfirmation} from './NamingConfirmation';
import {DeveloperInvocation} from './DeveloperInvocation';
import {SpecificationHistory} from './SpecificationHistory';
import {OracleHistory} from './OracleHistory';
import {HopDispatch} from './HopDispatch';
import {RunArtifacts} from './RunArtifacts';
import {QAReviewHistory} from './QAReviewHistory';
import {SdmDelivery} from './SdmDelivery';
import {ExecutionDiagnosis} from './ExecutionDiagnosis';
import {ExecutionReconciliation} from './ExecutionReconciliation';
import {ComparisonHistory} from './ComparisonHistory';
import './workflow.css';
import {WorkflowReadOnly,WorkflowQualifications} from './useWorkflowRefresh';
import {LegacyTaskRecords} from './LegacyTaskRecords';

const keys=['requirements','review','design','confirm','results','quality','delivery'];
const labels=['需求與資料規格','需求審查','流程設計審查','執行確認','執行與結果','品質審查','成果交付'];
const oldTabs:Record<string,string>={overview:'requirements',collaboration:'review',artifacts:'results',execution:'results'};
const time=(value:string)=>value?new Date(value).toLocaleString('zh-TW',{timeZone:'Asia/Taipei'}):'未記錄';

export function TaskWorkspace({task,tab,runId,navigate,renderSetup,renderValue}:{task:any;tab?:string;runId?:string;navigate:(path:string)=>void;renderSetup:(task:any)=>ReactNode;renderValue:(value:any)=>ReactNode}) {
  const base=`/projects/${encodeURIComponent(task.project_id)}/tasks/${encodeURIComponent(task.id)}`;
  const api=`/api/tasks/${encodeURIComponent(task.id)}`;
  const [runs,setRuns]=useState<any[]>([]),[detail,setDetail]=useState<any>(null),[workflow,setWorkflow]=useState<any>(null);
  const [error,setError]=useState(''),[loading,setLoading]=useState(true),[epoch,setEpoch]=useState(0);
  const [history,setHistory]=useState<any>(null),[historyError,setHistoryError]=useState('');
  const [pendingField,setPendingField]=useState('');
  const generation=useRef(0), refreshRunning=useRef(false), refreshQueued=useRef(false);
  const refs=useRef<Array<HTMLButtonElement|null>>([]);
  const stage=keys.includes(tab||'')?tab!:oldTabs[tab||'']||workflow?.current_stage||'requirements';
  const selected=runId||runs[0]?.run_id||'';
  const scope=useRef<any>(null);
  scope.current={workflow,loading,error,selected,stage};
  const stageInfo=workflow?.stages.find((s:any)=>s.key===stage);
  const select=(next:string,id=selected)=>navigate(`${base}/${next}${id?'/'+encodeURIComponent(id):''}`);

  const refresh=useCallback(async()=>{
    if(refreshRunning.current){refreshQueued.current=true;return}
    refreshRunning.current=true;
    const ticket=++generation.current;
    setLoading(true);setError('');
    try {
      const list=await request(`${api}/runs`);
      if(ticket!==generation.current)return;
      setRuns(list.runs);
      const id=runId||list.runs[0]?.run_id;
      if(runId&&!list.runs.some((r:any)=>r.run_id===runId))throw Error('指定版本不存在或不屬於此 Task；未改用最新版本。');
      if(!id){setDetail(null);setWorkflow(null);if(!keys.includes(tab||'')){window.history.replaceState(window.history.state,'',window.location.pathname+window.location.search+'#'+base+'/'+stage);window.dispatchEvent(new HashChangeEvent('hashchange'))}return}
      const [run,status]=await Promise.all([request(`${api}/runs/${id}`),request(`${api}/runs/${id}/workflow-status`)]);
      if(ticket!==generation.current)return;
      if(run.run_id!==id||status.run_id!==id||status.task_id!==task.id)throw Error('版本回應不一致，操作已暫停。');
      setDetail(run);setWorkflow(status);
      window.dispatchEvent(new CustomEvent('workbench:read-refresh',{detail:{path:`${api}/runs/${id}`}}));
      if(!runId||!keys.includes(tab||'')) {
        const canonical=`${base}/${!tab||tab==='overview'?status.current_stage:oldTabs[tab||'']||stage}/${encodeURIComponent(id)}`;
        window.history.replaceState(window.history.state,'',window.location.pathname+window.location.search+'#'+canonical);
        window.dispatchEvent(new HashChangeEvent('hashchange'));
      }
    }catch(e:any){if(ticket===generation.current)setError(e.message)}
    finally{if(ticket===generation.current)setLoading(false);refreshRunning.current=false;if(refreshQueued.current){refreshQueued.current=false;setEpoch(n=>n+1)}}
  },[api,runId,task.id,tab,base]);
  useEffect(()=>{setWorkflow(null);setDetail(null);setHistory(null)},[runId]);
  useEffect(()=>{generation.current++;void refresh();return()=>{generation.current++}},[refresh,epoch]);
  useEffect(()=>{
    const changed=(e:Event)=>{if((e as CustomEvent).detail?.path.startsWith(api)){setError('操作結果需要重新核對伺服器狀態。');setEpoch(n=>n+1)}};
    const before=(e:Event)=>{
      const path=(e as CustomEvent).detail?.path||'';
      if(!path.startsWith(api+'/'))return;
      const s=scope.current;
      if(s.loading||s.error||runId&&!s.workflow||s.workflow?.historical||s.workflow&&(!s.workflow.matches_current||!s.workflow.stages.find((x:any)=>x.key===s.stage)?.can_operate))e.preventDefault();
      const match=path.match(/\/runs\/([^/]+)\//);
      if(match&&match[1]!==s.selected)e.preventDefault();
    };
    window.addEventListener('workbench:changed',changed);window.addEventListener('workbench:before-write',before);
    return()=>{window.removeEventListener('workbench:changed',changed);window.removeEventListener('workbench:before-write',before)};
  },[api,runId]);
  useEffect(()=>{
    if(!workflow?.waiting)return;
    const poll=()=>{if(!document.hidden)setEpoch(n=>n+1)};
    const timer=window.setInterval(poll,5000);
    document.addEventListener('visibilitychange',poll);
    return()=>{clearInterval(timer);document.removeEventListener('visibilitychange',poll)};
  },[workflow?.waiting]);
  useEffect(()=>{
    const offline=()=>setError('網路已斷線，資訊過期。請恢復連線後重新核對，不能重送寫入。');
    const online=()=>setEpoch(n=>n+1);
    window.addEventListener('offline',offline);window.addEventListener('online',online);
    return()=>{window.removeEventListener('offline',offline);window.removeEventListener('online',online)};
  },[]);
  const runBase=`${api}/runs/${selected}`;
  const readonly=loading||!!error||workflow?.historical||workflow&&!workflow.matches_current||!!workflow&&!stageInfo?.can_operate;
  const valid=!!detail&&detail.run_id===selected&&workflow?.run_id===selected;
  useEffect(()=>{
    if(!pendingField||stage!=='requirements'||loading||error)return;
    const button=document.querySelector<HTMLButtonElement>('[data-revision-start]');
    button?.click();
    let frame=0,tries=0;
    const focus=()=>{const field=document.querySelector<HTMLElement>(`[data-field="${pendingField}"]`);if(field&&!field.matches(':disabled')){(field.matches('input,select,textarea,button')?field:field.querySelector<HTMLElement>('input:not(:disabled),select:not(:disabled),textarea:not(:disabled),button:not(:disabled)')||field)?.focus();field.scrollIntoView({block:'center'});setPendingField('')}else if(tries++<60)frame=requestAnimationFrame(focus);else setPendingField('')};
    frame=requestAnimationFrame(focus);
    return()=>cancelAnimationFrame(frame);
  },[pendingField,stage,loading,error]);
  const inspectHistory=async()=>{
    setHistoryError('');
    try{const [run,sa,dev,qa]=await Promise.all([request(runBase),request(runBase+'/sa-invocation'),request(runBase+'/developer'),request(runBase+'/qa-review')]);setHistory({run,sa,dev,qa})}
    catch(e:any){setHistory(null);setHistoryError(e.message)}
  };
  return <div className="wb-task-workspace workflow-panel">
    <div className="workflow-heading"><small>專案 {task.project_id}／{task.id}</small><h2>{task.name}</h2>
      <label>目前查看版本<select aria-label="共用 Run 版本" value={selected} disabled={loading} onChange={e=>select(stage,e.target.value)}>
        {!runs.some(r=>r.run_id===selected)&&<option value={selected}>{selected?'指定版本不可用':'尚無版本'}</option>}
        {runs.map((r,i)=><option key={r.run_id} value={r.run_id}>第 {runs.length-i} 版 · {r.run_id}{i?'（歷史）':'（最新）'}</option>)}
      </select></label>
      <p>{workflow?.category||'狀態待核對'} · 最後更新：{time(workflow?.updated_at)}{workflow?.historical?' · 歷史版本，只讀檢視':''}{workflow?.read_only_source?' · 既有真實案例，來源只讀':''}</p>
      <button disabled={loading} onClick={()=>setEpoch(n=>n+1)}>{loading?'讀取中…':'重新核對狀態'}</button>
    </div>
    <div role="tablist" aria-label="ETL 七個階段" className="workflow-stages">{keys.map((key,i)=><button key={key} ref={el=>{refs.current[i]=el}} id={`stage-${key}`} role="tab" aria-selected={stage===key} aria-controls={`stage-panel-${key}`} tabIndex={stage===key?0:-1} onClick={()=>select(key)} onKeyDown={e=>{
      const index=e.key==='ArrowRight'?(i+1)%7:e.key==='ArrowLeft'?(i+6)%7:e.key==='Home'?0:e.key==='End'?6:-1;
      if(index<0)return;e.preventDefault();select(keys[index]);refs.current[index]?.focus();
    }}><span>{i+1} · {labels[i]}</span><small>{({complete:'已有有效證據',current:'目前待處理',blocked:'前置條件待確認'} as any)[workflow?.stages[i]?.status]||'待讀取'}</small></button>)}</div>
    {error&&<p role="alert">資訊過期／無法確認：{error} 依賴新狀態的操作已停用；不會自動重送請求。</p>}
    {valid&&<section className="panel workflow-next" aria-label="目前狀態與下一步"><h3>第 {keys.indexOf(workflow.current_stage)+1} 階段：{labels[keys.indexOf(workflow.current_stage)]}</h3>
      <dl><dt>已完成</dt><dd>{workflow.completed.join('、')||'尚無有效核准'}</dd><dt>現在需要誰</dt><dd>{workflow.owner}</dd><dt>下一步</dt><dd>{workflow.next_action.label}</dd></dl>
      <button className="primary" disabled={loading||!!error} onClick={()=>{select(workflow.next_action.stage);requestAnimationFrame(()=>document.getElementById(`stage-panel-${workflow.next_action.stage}`)?.scrollIntoView({block:'start'}))}}>前往{labels[keys.indexOf(workflow.next_action.stage)]}</button>
      {workflow.service_blocked_reason&&<p role="status">{workflow.service_blocked_reason}</p>}
      {workflow.execution_blocked_reason&&workflow.current_stage==='confirm'&&<p>{workflow.execution_blocked_reason}</p>}
      <details><summary>來源支援與驗收範圍</summary><p>{workflow.source_scope_note}</p></details>
    </section>}
    {stageInfo?.blocked_reason&&<p role="status">{stageInfo.blocked_reason} 此階段可檢視，操作須等前置條件成立。</p>}
    {valid&&!!workflow.issues.length&&<section className="panel workflow-issues" aria-label="問題處理區"><h3>待處理問題</h3><ul>{workflow.issues.map((issue:any,i:number)=><li key={i}><b>{issue.message}</b><p>原因：{issue.issue_type||issue.code||'審查缺口'} · 對應欄位：{issue.field_path||issue.evidence_ids?.join('、')||'需求說明'}</p><button disabled={loading||!!error||workflow.historical} onClick={()=>{if(issue.stage){select(issue.stage);return}const path=issue.field_path||issue.evidence_ids?.[0]||'';setPendingField(/write_mode/.test(path)?'write_mode':/date_scope|date_column|start_date|end_date/.test(path)?'date_scope':/key_columns/.test(path)?'key_columns':/join/.test(path)?'join':/transformation|filter|aggregation/.test(path)?'transformation':/source|csv|excel|json/.test(path)?'source':/schema/.test(path)?'target_schema':/table/.test(path)?'target_table':'requirement_text');select('requirements')}}>{issue.stage==='quality'?'檢視 QA 意見與補證':issue.stage==='design'?'檢視並修正规格':'前往修正'}</button></li>)}</ul></section>}
    <WorkflowQualifications.Provider value={workflow?.operation_qualifications||{}}><WorkflowReadOnly.Provider value={!!readonly}>
    <section className="panel" hidden={stage!=='requirements'} role="tabpanel" id="stage-panel-requirements" aria-labelledby="stage-requirements">
      {(!runId||valid)&&<fieldset className="workflow-controls" disabled={loading||!!error}><RunVersions taskId={task.id} requestedRunId={selected||undefined} onSelectRun={id=>select('requirements',id)}/></fieldset>}
      <details><summary>Task 保存設定（目前內容；版本輸入以上方不可變快照為準）</summary>{renderSetup(task)}</details>
    </section>
    {valid&&stage!=='requirements'&&<section className="panel" role="tabpanel" id={`stage-panel-${stage}`} aria-labelledby={`stage-${stage}`}>
      <fieldset className="workflow-controls" disabled={loading||!!error}>
        {stage==='review'&&<><SAInvocation key={selected} taskId={task.id} runId={selected}/><details><summary>需求審查技術證據</summary><SAEvidence taskId={task.id} runId={selected}/></details></>}
        {stage==='design'&&<><NamingConfirmation taskId={task.id} runId={selected} historical={workflow.historical||!workflow.matches_current||detail.write_started} editable={!readonly&&!detail.write_started} sourceOrder={detail.input_summary.source_order_v1}/><DeveloperInvocation key={selected} taskId={task.id} runId={selected}/><SpecificationHistory key={selected} taskId={task.id} runId={selected}/></>}
        {stage==='confirm'&&<><p>本版目標：{detail.input_summary.target_schema}.{detail.input_summary.target_table} · 寫入方式：{detail.input_summary.requirements_v1?.write_mode||'未確認'}</p><OracleHistory taskId={task.id} requestedRunId={selected} stage="confirm"/><HopDispatch key={selected} taskId={task.id} runId={selected}/></>}
        {stage==='results'&&<><RunArtifacts taskId={task.id} requestedRunId={selected}/><ComparisonHistory taskId={task.id} runId={selected}/>{['HOP_EXECUTION_FAILED','HOP_RESULT_UNKNOWN'].includes(detail.outcome_code)&&<><ExecutionDiagnosis base={runBase}/><ExecutionReconciliation base={runBase} onSaved={async()=>setEpoch(n=>n+1)}/></>}<HopDispatch key={selected} taskId={task.id} runId={selected}/></>}
        {stage==='quality'&&<><QAReviewHistory key={selected} taskId={task.id} runId={selected}/>{detail.qa_revision&&<button disabled={readonly} onClick={()=>{setPendingField('target_table');select('requirements')}}>建立修正版（保留原始執行，使用新目標）</button>}</>}
      </fieldset>
      {stage==='delivery'&&<SdmDelivery key={selected} base={runBase}/>}
    </section>}
    </WorkflowReadOnly.Provider></WorkflowQualifications.Provider>
    <details className="panel"><summary>審查／修訂時間軸與技術詳情</summary><button onClick={inspectHistory}>讀取此版本完整紀錄</button>{historyError&&<p role="alert">{historyError}</p>}{history&&<><ol>{history.run.events?.map((event:any)=><li key={event.event_id}>{time(event.created_at)} · {event.event_type}{renderValue(event.event_context)}</li>)}</ol><details><summary>SA／Developer／QA 模型紀錄與用量</summary>{renderValue({sa:history.sa,developer:history.dev,qa:history.qa})}</details></>}</details>
    <LegacyTaskRecords task={task} renderValue={renderValue}/>
  </div>;
}
