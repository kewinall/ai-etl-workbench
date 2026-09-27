import {useEffect, useState} from 'react';
import {request} from './api';
import {ExecutionDiagnosis} from './ExecutionDiagnosis';

export function RunArtifacts({taskId}:{taskId:string}) {
  const [runs,setRuns]=useState<any[]>([]),[selected,setSelected]=useState('');
  const [data,setData]=useState<any>(null),[error,setError]=useState(''),[node,setNode]=useState('');
  const [refresh,setRefresh]=useState(0),[pending,setPending]=useState(true);
  const base=`/api/tasks/${encodeURIComponent(taskId)}/runs`;
  useEffect(()=>{let live=true;setError('');request(base).then(r=>{if(live){setRuns(r.runs);setSelected(s=>r.runs.some((x:any)=>x.run_id===s)?s:r.runs[0]?.run_id||'');if(!r.runs.length)setPending(false)}}).catch(e=>{if(live){setError(e.message);setPending(false)}});return()=>{live=false}},[base,refresh]);
  useEffect(()=>{let live=true;setData(null);setNode('');setError('');if(!selected)return;setPending(true);
    request(`${base}/${selected}/artifacts`).then(r=>live&&setData(r)).catch(e=>live&&setError(e.message)).finally(()=>live&&setPending(false));return()=>{live=false}},[base,selected,refresh]);
  const chosen=runs.find(r=>r.run_id===selected), detail=data?.nodes?.find((n:any)=>n.id===node);
  return <section className="panel" aria-label="版本流程與產物"><h3>版本流程與產物</h3>
    <p>以下是指定 Run 核准時的編譯內容及保存的節點計數，不是舊版 Task 節點。檢視不會重新執行；正式下載請至「交付」。</p>
    <button onClick={()=>setRefresh(n=>n+1)}>重新讀取版本產物</button>
    {!!runs.length&&<label>流程版本<select value={selected} onChange={e=>setSelected(e.target.value)}>{runs.map(r=><option key={r.run_id} value={r.run_id}>{new Date(r.created_at).toLocaleString()} · {r.state} · {r.run_id}</option>)}</select></label>}
    {error&&<p role="alert">無法讀取版本產物：{error}</p>}{pending&&<p role="status">正在讀取版本產物…</p>}
    {!pending&&!error&&!runs.length&&<p>尚無 Run；下方保留舊版產物。</p>}
    {data?.status==='NO_AUTHORIZED_COMPILER_ARTIFACTS'&&<p>此版本尚未核准執行，沒有可追溯的已核准編譯產物。</p>}
    {data?.scope&&<><p>Hop 保存結果：{data.execution?.result.status||'尚無終止證據'}；節點證據：{data.execution?.complete_node_evidence?'完整':'未完整／未執行'}。這不等於 QA 或 Release 核准。</p>
      <div className="wb-run-nodes">{data.nodes.map((n:any)=><button key={n.id} className="wb-run-node" aria-pressed={node===n.id} onClick={()=>setNode(n.id)}><b>{n.id}</b><small>{n.component}</small><span>{n.counters?`錯誤 ${n.counters.errors}`:'無計數證據'}</span></button>)}</div>
      {detail&&<article className="wb-record" aria-label="Run 節點詳細資訊"><h4>{detail.id} · {detail.component}</h4><p>程式工具／Hop 元件，非 AI 角色。</p>{detail.counters?<dl>{Object.entries(detail.counters).map(([k,v])=><div key={k}><dt>{k}</dt><dd>{String(v)}</dd></div>)}</dl>:<p>此節點沒有保存的計數，不推定為零或成功。</p>}<details><summary>編譯節點定義</summary><pre>{JSON.stringify(data.plan.stages.find((s:any)=>s.id===detail.id)||{id:detail.id,component:detail.component},null,2)}</pre></details></article>}
      <ul>{data.edges.map((e:any,i:number)=><li key={i}>{e.from_node} → {e.to_node}</li>)}</ul>
      {data.artifacts.map((a:any)=><details key={a.kind}><summary>{a.kind} · 檢視已核准編譯內容</summary><p>SHA-256：{a.checksum}</p><pre>{a.content}</pre></details>)}
    </>}
    {chosen&&['HOP_EXECUTION_FAILED','HOP_RESULT_UNKNOWN'].includes(chosen.outcome_code)&&<ExecutionDiagnosis key={selected} base={`${base}/${selected}`}/>}
  </section>;
}
