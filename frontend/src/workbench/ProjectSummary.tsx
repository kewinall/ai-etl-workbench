import {useEffect,useState} from 'react';
import {request} from './api';

const order=['待你確認','需修正','待核對','系統處理中','執行服務未就緒','可交付','待確認'];
export function ProjectSummary({projectId}:{projectId:string}){
 const [attempt,retry]=useState(0),[data,setData]=useState<any>(null),[error,setError]=useState(''),[busy,setBusy]=useState(true);
 useEffect(()=>{
  let live=true;setBusy(true);setData(null);setError('');
  request<any>(`/api/projects/${projectId}/summary`).then(value=>{
   if(value.project_id!==projectId||value.basis!=='LATEST_RUN_PER_TASK')throw Error('摘要與目前專案不一致');
   if(live)setData(value);
  }).catch(e=>live&&setError(e.message)).finally(()=>live&&setBusy(false));
  return()=>{live=false};
 },[projectId,attempt]);
 const labels:Record<string,string>={NO_RUN:'尚未建立準備版本',QUEUED:'排隊／待輸入確認',RUNNING:'處理中',NEEDS_REVIEW:'Run 開啟中（含待檢閱與已交付）',FAILED:'Run 失敗',CANCELLED:'Run 已取消',SUCCEEDED:'Run 已結束（非交付核准）'};
 const counts=data?.workflow_counts as Record<string,number>|null|undefined;
 return <section className="panel" aria-label="專案進度摘要">
  <h3>專案進度</h3><p>每個 Task 只看最新 Run，與 Task 卡片及篩選使用相同的工作流程判定（含 QA 與交付證據）。</p>
  <button disabled={busy} onClick={()=>retry(n=>n+1)}>更新專案摘要</button>
  {busy?<p role="status">正在讀取專案摘要…</p>:error?<p role="alert">{error}</p>:data&&<>
   <p>共 {data.task_count} 個 Task</p>
   {counts?<dl className="wb-summary-counts">{Object.entries(counts).sort(([a],[b])=>order.indexOf(a)-order.indexOf(b)).map(([category,count])=><div key={category}><dt>{category}</dt><dd>{count}</dd></div>)}</dl>
    :<p role="alert">工作流程狀態待確認：無法核對 QA／交付證據，請重試；下方 Run 狀態不代表完成或待補正。</p>}
   {!!data.workflow_unverified&&<p role="status">{data.workflow_unverified} 個 Task 狀態待確認，已單獨計入「待確認」，不視為零筆或完成。</p>}
   <details><summary>原始 Run 狀態（技術參考）</summary><dl className="wb-summary-counts">{data.states.map((item:any)=><div key={item.state}><dt>{labels[item.state]||item.state}</dt><dd>{item.count}</dd></div>)}</dl></details>
  </>}
 </section>;
}
