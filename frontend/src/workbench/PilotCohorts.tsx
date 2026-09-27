import {useEffect,useRef,useState} from 'react';
import {request,jsonBody} from './api';
import {OperationLatch} from './operationLatch';

const scenarioNames:Record<string,string>={SUCCESS:'正常成功',REQUIREMENT_GAP:'需求缺口',SEMANTIC_DEFECT:'語意缺陷',EXECUTION_RECOVERY:'失敗修復'};

export function PilotCohorts({projectId,navigate}:{projectId:string;navigate:(path:string)=>void}) {
  const [data,setData]=useState<any>(null),[tasks,setTasks]=useState<any[]>([]);
  const [error,setError]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false);
  const [selection,setSelection]=useState<Record<string,string>>({}),[attempt,retry]=useState(0);
  const latch=useRef(new OperationLatch());
  useEffect(()=>{
    let live=true;setData(null);setError('');setSelection({});setMessage('');
    Promise.all([request(`/api/projects/${projectId}/pilot-cohorts`),request(`/api/projects/${projectId}/tasks`)])
      .then(([value,items])=>{
        if(value.project_id!==projectId||!Array.isArray(value.cohorts)||!Array.isArray(items))throw Error('案例集合回應不完整');
        if(live){setData(value);setTasks(items)}
      }).catch(e=>{if(live)setError(e.message)});
    return()=>{live=false};
  },[projectId,attempt]);
  const bind=async(cohortId:string,caseKey:string)=>{
    const key=`${cohortId}:${caseKey}`,taskId=selection[key];
    if(!taskId||!latch.current.acquire())return;
    setBusy(true);setMessage('');
    try{
      await request(`/api/projects/${projectId}/pilot-cohorts/${cohortId}/cases/${encodeURIComponent(caseKey)}/task`,jsonBody('POST',{task_id:taskId}));
      const updated=await request(`/api/projects/${projectId}/pilot-cohorts`);
      if(updated.project_id!==projectId||!Array.isArray(updated.cohorts))throw Error('綁定後回讀資料不完整');
      setData(updated);setMessage('案例已綁定並重新讀取；這不代表執行或驗收通過。');
    }catch(e:any){setMessage(e.message)}finally{latch.current.release();setBusy(false)}
  };
  return <section className="pilot-cohorts" aria-label="正式 Pilot 案例集合">
    <h3>正式比較案例</h3>
    <p>登錄後分母固定 20 案。只能綁定同專案、尚無 Run 的 Task；綁定後不能改選，所有失敗與取消版本都保留。樣本指紋尚須逐案驗證。</p>
    <button disabled={busy} onClick={()=>retry(n=>n+1)}>重新讀取案例集合</button>
    {error?<p role="alert">{error}</p>:!data?<p role="status">正在讀取案例集合…</p>:<>
      {!data.cohorts.length&&<p>尚未登錄比較集合。20 案樣本與答案須先固定指紋；現有歷史 Run 不會自動當成正式比較案例。</p>}
      {data.cohorts.map((cohort:any)=><article key={cohort.cohort_id}>
        <h4>{cohort.name}</h4><p>固定分母：{cohort.registered_cases}；已綁定：{cohort.bound_cases}；成效比較：尚未完成。</p>
        {cohort.cases.map((item:any)=>{const key=`${cohort.cohort_id}:${item.case_key}`;return <details key={key}>
          <summary>{item.ordinal}. {item.definition.title} · {scenarioNames[item.definition.scenario]||item.definition.scenario} · {item.task_id?'已綁定':'待綁定'}</summary>
          <p>{item.definition.acceptance}</p>
          <p>樣本：{item.definition.fixture_reference}；答案：{item.definition.oracle_reference}</p>
          <p>樣本指紋：<code>{item.definition.fixture_checksum||'缺少'}</code></p>
          <p>答案指紋：<code>{item.definition.oracle_checksum||'缺少'}</code></p>
          {item.task_id?<p>Task：{item.task_id}</p>:<fieldset disabled={busy}>
            <label>選擇案例 {item.case_key} 的 Task<select value={selection[key]||''} onChange={e=>setSelection({...selection,[key]:e.target.value})}>
              <option value="">請明確選擇（已開始的 Task 會被伺服器拒絕）</option>
              {tasks.map(task=><option key={task.id} value={task.id}>{task.name} · {task.id}</option>)}
            </select></label>
            <button disabled={!selection[key]} onClick={()=>bind(cohort.cohort_id,item.case_key)}>確認固定綁定案例 {item.case_key}</button>
          </fieldset>}
          {!item.runs.length?<p>尚無 Run 證據；不算通過。</p>:item.runs.map((run:any)=><p key={run.run_id}>
            {run.state} · {run.outcome_code||'尚無結果'} · {run.run_id}{' '}
            <button onClick={()=>navigate(`/projects/${projectId}/tasks/${encodeURIComponent(item.task_id)}/execution/${run.run_id}`)}>查看此 Run 證據</button>
          </p>)}
        </details>})}
      </article>)}
    </>}
    {message&&<p role="status">{message}</p>}
  </section>;
}
