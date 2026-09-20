import {useEffect,useState} from 'react';
import {request} from './api';

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
 const labels:Record<string,string>={NO_RUN:'尚未建立準備版本',QUEUED:'排隊／待輸入確認',RUNNING:'處理中',NEEDS_REVIEW:'等待檢閱或補正',FAILED:'Run 失敗',CANCELLED:'Run 已取消',SUCCEEDED:'Run 已結束（非交付核准）'};
 return <section className="panel" aria-label="專案進度摘要">
  <h3>專案進度</h3><p>每個 Task 只計算最新 Run；不以歷史成功標記判斷 QA 或交付完成。</p>
  <button disabled={busy} onClick={()=>retry(n=>n+1)}>更新專案摘要</button>
  {busy?<p role="status">正在讀取專案摘要…</p>:error?<p role="alert">{error}</p>:data&&<>
   <p>共 {data.task_count} 個 Task</p>
   <dl style={{display:'flex',gap:'1rem',flexWrap:'wrap'}}>{data.states.map((item:any)=><div key={item.state}><dt>{labels[item.state]||item.state}</dt><dd>{item.count}</dd></div>)}</dl>
   <p>請到「歷史 Task」開啟工作項目，查看阻擋原因與下一步；此摘要未評估 QA／Release 資格。</p>
  </>}
 </section>;
}
