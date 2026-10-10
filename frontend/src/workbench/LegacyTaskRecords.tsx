import {useEffect,useState,type ReactNode} from 'react';
import {request} from './api';

export function LegacyTaskRecords({task,renderValue}:{task:any;renderValue:(value:any)=>ReactNode}) {
  const [assets,setAssets]=useState<any>(null),[error,setError]=useState(''),[selected,setSelected]=useState('');
  const node=task.nodes?.find((n:any)=>n.key===selected);
  const metadata=!!(task.nodes?.length||task.logs?.length||task.last_error||task.error_test_result);
  useEffect(()=>{let live=true;if(!metadata)request(`/api/tasks/${encodeURIComponent(task.id)}/history-assets`).then(value=>live&&setAssets(value)).catch(e=>live&&setError(e.message));return()=>{live=false}},[task.id,metadata]);
  if(!metadata&&!error&&(!assets||!assets.jobs?.length&&!assets.sql?.length&&!assets.hop_logs?.length))return null;
  return <details className="panel"><summary>舊版紀錄：Task 節點、Log、Hop、SQL 與下載</summary>
    <p>這些是舊版 Task 保存內容；不代表目前查看 Run 的執行或有效核准。</p>
    <h3>舊版節點</h3>{task.nodes?.map((n:any)=><button key={n.key} aria-pressed={selected===n.key} onClick={()=>setSelected(n.key)}>{n.label} · {n.status}</button>)}
    {node&&<section aria-label="舊版節點詳情"><h4>{node.label}</h4>{renderValue(node.detail||{})}{renderValue(task.logs?.filter((log:any)=>log.node===node.key)||[])}</section>}
    <details><summary>舊版 Task Log 與錯誤紀錄</summary>{renderValue({logs:task.logs,last_error:task.last_error,error_test_result:task.error_test_result})}</details>
    <button onClick={async()=>{try{setAssets(await request(`/api/tasks/${encodeURIComponent(task.id)}/history-assets`));setError('')}catch(e:any){setError(e.message)}}}>讀取舊版產物</button>
    {error&&<p role="alert">{error}</p>}
    {assets&&<><h3>舊版 Hop 流程與下載</h3>{assets.jobs?.map((job:any)=><article key={job.artifact_id}><h4>{job.name} · v{job.version}</h4>{job.download_url&&<a href={job.download_url}>下載舊版 {job.name}</a>}{renderValue({transforms:job.transforms,hops:job.hops})}<details><summary>XML／完整定義</summary><pre>{job.content}</pre></details></article>)}
      <h3>舊版 SQL</h3>{assets.sql?.map((sql:any,i:number)=><details key={i}><summary>{sql.artifact} · {sql.node}</summary><pre>{sql.sql}</pre></details>)}
      <h3>舊版 Apache Hop Log</h3>{assets.hop_logs?.map((log:any,i:number)=><details key={i}><summary>{log.log_type}</summary><pre>{log.log_content}</pre></details>)}
    </>}
  </details>;
}
