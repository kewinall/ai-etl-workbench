import {useEffect,useState} from 'react';
import {request,jsonBody} from './api';
import {SdmHistory} from './SdmHistory';
import {FormalRelease} from './FormalRelease';

export function SdmDelivery({base}:{base:string}){
 const [approval,setApproval]=useState<any>(null),[busy,setBusy]=useState(true),[error,setError]=useState(''),[saved,setSaved]=useState<any>(null),[revision,setRevision]=useState(0);
 useEffect(()=>{
  let live=true;setApproval(null);setSaved(null);setError('');setBusy(true);
  request(`${base}/qa-approval`).then(a=>{if(live)setApproval(a)}).catch(e=>{if(live)setError(e.message)}).finally(()=>{if(live)setBusy(false)});
  return()=>{live=false};
 },[base,revision]);
 async function prepare(){
  if(busy||approval?.status!=='APPROVED_CURRENT'||!approval.binding?.checksum)return;
  setBusy(true);setError('');setSaved(null);
  try{
   const value=await request(`${base}/sdm-delivery`,jsonBody('POST',{qa_binding_checksum:approval.binding.checksum}));
   if(value.release_ready!==false||value.qa_binding?.status!=='QA_LINKED_NOT_RELEASED')throw new Error('SDM 回應狀態不符，請重新載入');
   setSaved(value);
  }catch(e){setApproval(null);setError(e instanceof Error?e.message:'SDM 產生失敗');}
  finally{setBusy(false)}
 }
 return <section aria-label="SDM 交付準備" style={{overflowWrap:'anywhere'}}>
  <h4>已執行版本的 SDM</h4><p>須先在「執行與 QA」核准目前版本；此操作產生候選文件並綁定 QA，不會直接開放 Release。</p>
  {error&&<p role="alert">{error}</p>}
  {!busy&&approval&&approval.status!=='APPROVED_CURRENT'&&<p>此版本尚無有效人工 QA 核准，不能準備交付文件。</p>}
  <button disabled={busy||approval?.status!=='APPROVED_CURRENT'} onClick={prepare}>{busy?'處理中…':'產生／取得 QA 關聯 SDM'}</button>
  <button disabled={busy} onClick={()=>setRevision(n=>n+1)}>重新核對交付條件</button>
  {saved&&<p role="status">SDM 已保存並關聯 QA；請由下方歷史文件下載。尚未完成 Release 驗證。</p>}
  <SdmHistory key={`history:${base}:${saved?.document?.sdm_id||''}`} base={base}/>
  <FormalRelease key={`release:${base}:${saved?.document?.sdm_id||''}`} base={base}/>
 </section>;
}
