import {useEffect,useState} from 'react';
import {request,jsonBody} from './api';

export function QAApproval({taskId,runId}:{taskId:string;runId:string}) {
  const [data,setData]=useState<any>(null),[busy,setBusy]=useState(true),[confirmed,setConfirmed]=useState(false),[error,setError]=useState(''),[reload,setReload]=useState(0);
  const url=`/api/tasks/${encodeURIComponent(taskId)}/runs/${runId}/qa-approval`;
  useEffect(()=>{
    let live=true;setData(null);setConfirmed(false);setError('');setBusy(true);
    request(url).then(value=>{if(live)setData(value)}).catch(e=>{if(live)setError(e.message)})
      .finally(()=>{if(live)setBusy(false)});
    return()=>{live=false};
  },[url,reload]);
  async function approve(){
    if(busy||!confirmed||data?.status!=='AWAITING_CONFIRMATION'||!data.binding?.checksum)return;
    setBusy(true);setError('');
    try{
      await request(url,jsonBody('POST',{confirmed:true,binding_checksum:data.binding.checksum}));
      setData(null);setConfirmed(false);setReload(n=>n+1);
    }catch(e){setData(null);setConfirmed(false);setError(e instanceof Error?e.message:'核准失敗，請重新載入');setBusy(false)}
  }
  return <section aria-label="人工 QA 核准" className="wb-record" style={{overflowWrap:'anywhere'}}>
    <h4>人工 QA 核准</h4><p>核准只適用於下列版本的 QA 證據，不代表 Release 已可交付。</p>
    {busy&&<p role="status">正在處理核准狀態…</p>}
    {error&&<p role="alert">{error}</p>}
    {!busy&&data?.status==='NOT_ELIGIBLE'&&<p>尚無目前版本的完整 QA PASS 審查，不能核准。</p>}
    {data?.status==='APPROVED_CURRENT'&&<p>目前版本已由操作者核准。</p>}
    {data?.status==='STALE_APPROVAL'&&<p>此為已失效的歷史核准；請重新完成目前版本的審查。</p>}
    {data?.approval&&<p>核准紀錄：{data.approval.approval_id}</p>}
    {data?.status==='AWAITING_CONFIRMATION'&&<>
      <details><summary>待核准版本</summary><p>規格：{data.binding.specification_checksum}</p><p>審查結果：{data.binding.review_checksum}</p><p>核准版本：{data.binding.checksum}</p></details>
      <label><input type="checkbox" checked={confirmed} disabled={busy} onChange={e=>setConfirmed(e.target.checked)}/>我已檢視本 Run 的規格、執行與 QA 證據，確認此版本</label>
      <button disabled={busy||!confirmed} onClick={approve}>核准此版本 QA</button>
    </>}
    <button disabled={busy} onClick={()=>setReload(n=>n+1)}>重新讀取核准狀態</button>
  </section>;
}
