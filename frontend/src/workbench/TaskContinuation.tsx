import {useEffect,useState} from 'react';
import {request} from './api';

const pick=(w:any)=>w&&{category:w.category,current_stage:w.current_stage,waiting:w.waiting,delivered:w.delivered,
  effective_status:w.effective_status,next:typeof w.next_action==='string'?w.next_action:w.next_action?.label};

// Shows the project summary's projection first; only re-reads the Task workflow while it is waiting or unverified.
export function TaskContinuation({task,projectId,navigate}:{task:any;projectId?:string;navigate:(path:string)=>void}) {
  const id=task.latest_run?.run_id;
  const [status,setStatus]=useState<any>(()=>pick(task.workflow)),[error,setError]=useState(''),[attempt,setAttempt]=useState(0);
  useEffect(()=>{
    let live=true;setError('');
    if(!id){setStatus(null);return}
    const initial=pick(task.workflow);
    setStatus(initial);
    let waiting=!!initial?.waiting,inflight=false;
    const load=async()=>{if(inflight)return;inflight=true;try{const result=await request(`/api/tasks/${encodeURIComponent(task.id)}/runs/${id}/workflow-status`);if(result.run_id!==id||result.task_id!==task.id)throw Error('版本摘要不一致');if(live){waiting=result.waiting;setStatus(pick(result));setError('')}}catch(e:any){if(live){waiting=false;setStatus(null);setError(e.message)}}finally{inflight=false}};
    if(!initial||attempt)void load();
    const timer=window.setInterval(()=>{if(waiting&&!document.hidden)void load()},5000);
    return()=>{live=false;clearInterval(timer)};
  },[task.id,id,attempt,task.workflow]);
  const label=status?.category||(!id?'待你確認':error?'待確認':'讀取接續狀態中…');
  return <article className="wb-history-row"><span><strong>{task.name}</strong><small>{task.id} · {task.source} → {task.target}</small><small>{id?`Run ${id}`:'尚無準備版本'}</small><small><b>{label}</b>{status?.effective_status?` · ${status.effective_status}`:''}{status?.next?` · 下一步：${status.next}`:''}</small>{error&&<small role="alert">{error}</small>}</span><span>
    <button disabled={!!id&&!status} onClick={()=>navigate(`/projects/${projectId}/tasks/${encodeURIComponent(task.id)}/${status?.current_stage||'requirements'}${id?'/'+encodeURIComponent(id):''}`)}>{status?.delivered?'查看':'繼續處理'} {task.name}</button>
    {(error||!status&&id)&&<button onClick={()=>setAttempt(n=>n+1)}>重新核對 {task.name}</button>}
  </span></article>;
}
