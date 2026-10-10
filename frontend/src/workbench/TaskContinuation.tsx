import {useEffect,useState} from 'react';
import {request} from './api';

export function TaskContinuation({task,projectId,navigate}:{task:any;projectId?:string;navigate:(path:string)=>void}) {
  const [status,setStatus]=useState<any>(null),[error,setError]=useState(''),[attempt,setAttempt]=useState(0);
  const id=task.latest_run?.run_id;
  useEffect(()=>{
    let live=true;setStatus(null);setError('');
    if(!id)return;
    let waiting=false,inflight=false;
    const load=async()=>{if(inflight)return;inflight=true;try{const result=await request(`/api/tasks/${encodeURIComponent(task.id)}/runs/${id}/workflow-status`);if(result.run_id!==id||result.task_id!==task.id)throw Error('版本摘要不一致');if(live){waiting=result.waiting;setStatus(result);setError('')}}catch(e:any){if(live){waiting=false;setStatus(null);setError(e.message)}}finally{inflight=false}};
    void load();
    const timer=window.setInterval(()=>{if(waiting&&!document.hidden)void load()},5000);
    return()=>{live=false;clearInterval(timer)};
  },[task.id,id,attempt]);
  return <article className="wb-history-row"><span><strong>{task.name}</strong><small>{task.id} · {task.source} → {task.target}</small><small>{id?`Run ${id}`:'尚無準備版本'}</small><small>{status?.category||(!id?'待你確認':error?'狀態待核對':'讀取接續狀態中…')}</small>{error&&<small role="alert">{error}</small>}</span><span>
    <button disabled={!!id&&!status} onClick={()=>navigate(`/projects/${projectId}/tasks/${encodeURIComponent(task.id)}/${status?.current_stage||'requirements'}${id?'/'+encodeURIComponent(id):''}`)}>繼續處理 {task.name}</button>
    {error&&<button onClick={()=>setAttempt(n=>n+1)}>重新核對 {task.name}</button>}
  </span></article>;
}
