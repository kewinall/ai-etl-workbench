import {useEffect,useState} from 'react';
import {request} from './api';
import {OracleEditor} from './OracleEditor';
import {OracleReview} from './OracleReview';
import {ComparisonHistory} from './ComparisonHistory';
import {QAReviewHistory} from './QAReviewHistory';

export function OracleHistory({taskId}:{taskId:string}) {
  const canLeave=()=>window.dispatchEvent(new Event('workbench:before-navigate',{cancelable:true}));
  const [runs,setRuns]=useState<any[]>([]),[run,setRun]=useState('');
  const [specs,setSpecs]=useState<any[]>([]),[spec,setSpec]=useState('');
  const [items,setItems]=useState<any[]>([]),[error,setError]=useState('');
  const [loading,setLoading]=useState(true),[refresh,setRefresh]=useState(0);
  useEffect(()=>{
    let live=true;setLoading(true);setError('');setRuns([]);setRun('');setSpecs([]);setSpec('');setItems([]);
    request(`/api/tasks/${encodeURIComponent(taskId)}/runs`).then(data=>{if(live){setRuns(data.runs);setRun(data.runs[0]?.run_id||'')}})
      .catch(e=>live&&setError(e.message)).finally(()=>live&&setLoading(false));
    return()=>{live=false};
  },[taskId,refresh]);
  useEffect(()=>{
    let live=true;setSpecs([]);setSpec('');setItems([]);if(!run)return;
    setLoading(true);setError('');
    request(`/api/tasks/${encodeURIComponent(taskId)}/runs/${run}/specifications`).then(data=>{if(live){setSpecs(data.items);setSpec(data.items[0]?.specification_id||'')}})
      .catch(e=>live&&setError(e.message)).finally(()=>live&&setLoading(false));
    return()=>{live=false};
  },[taskId,run]);
  useEffect(()=>{
    let live=true;setItems([]);if(!run||!spec)return;
    setLoading(true);setError('');
    request(`/api/tasks/${encodeURIComponent(taskId)}/runs/${run}/specifications/${spec}/oracles`).then(data=>live&&setItems(data.items))
      .catch(e=>live&&setError(e.message)).finally(()=>live&&setLoading(false));
    return()=>{live=false};
  },[taskId,run,spec]);
  return <section className="panel" aria-label="標準答案版本紀錄" style={{overflowWrap:'anywhere'}}>
    <h3>標準答案版本紀錄</h3><p>核准紀錄僅代表當時的人工確認，不表示目前仍有效、已執行或 QA 通過。可按「查看答案內容」讀取指定歷史版本。</p>
    <button disabled={loading} onClick={()=>{if(canLeave())setRefresh(n=>n+1)}}>重新讀取標準答案</button>
    {!!runs.length&&<label>準備版本<select aria-label="標準答案準備版本" value={run} onChange={e=>{if(canLeave()){setSpec('');setItems([]);setRun(e.target.value)}}}>{runs.map(r=><option key={r.run_id} value={r.run_id}>{r.run_id} · {r.state}</option>)}</select></label>}
    {!!specs.length&&<label>規格版本<select aria-label="標準答案規格版本" value={spec} onChange={e=>{if(canLeave()){setItems([]);setSpec(e.target.value)}}}>{specs.map(s=><option key={s.specification_id} value={s.specification_id}>第 {s.version} 版{s.approval_effective?' · 規格核准有效':' · 規格待重新檢查'}</option>)}</select></label>}
    {loading&&<p role="status">正在讀取標準答案紀錄…</p>}
    {error&&<p role="alert">無法讀取標準答案：{error}。請重新讀取。</p>}
    {!loading&&!error&&!items.length&&<p>{!runs.length?'尚無準備版本。':!specs.length?'此準備版本尚無已保存規格。':'此規格尚未保存標準答案。'}</p>}
    {items.map(item=><article className="wb-record" key={item.oracle_id}><h4>答案第 {item.version} 版</h4><p>{item.approval_recorded?'曾人工核准；目前資格尚未評估':'尚無人工核准紀錄'}</p><p>保存時間：{new Date(item.created_at).toLocaleString()}</p>{item.approved_at&&<p>核准時間：{new Date(item.approved_at).toLocaleString()}</p>}<details><summary>版本指紋</summary><p>{item.document_checksum}</p></details><p>尚不能據此判定 QA 通過或可交付。</p><OracleReview url={`/api/tasks/${encodeURIComponent(taskId)}/runs/${run}/specifications/${spec}/oracles/${item.oracle_id}/review`} checksum={item.document_checksum}/></article>)}
    {specs.find(s=>s.specification_id===spec)?.approval_effective&&<OracleEditor key={run+'/'+spec} base={`/api/tasks/${encodeURIComponent(taskId)}/runs/${run}/specifications/${spec}`} onHistory={setItems}/>}
    {spec&&!specs.find(s=>s.specification_id===spec)?.approval_effective&&<p>請先至需求與規格核准有效規格，才能輸入答案。</p>}
    {run&&<ComparisonHistory key={run} taskId={taskId} runId={run}/>}
    {run&&<QAReviewHistory key={'qa-'+run} taskId={taskId} runId={run}/>}
  </section>;
}
