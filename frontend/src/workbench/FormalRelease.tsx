import {useEffect,useState} from 'react';
import {request,jsonBody} from './api';

const labels:Record<string,string>={PREREQUISITES_REQUIRED:'需完成真實角色協作、Hop 執行及人工 QA 核准',
 SDM_AND_CANDIDATE_REQUIRED:'待產生 QA 關聯 SDM 與候選 ZIP',PORTABILITY_REQUIRED:'待隔離環境可攜驗證',
 EVIDENCE_CHANGED:'證據有異動，交付已阻擋',AWAITING_RELEASE_APPROVAL:'驗證完成，待人工核准交付',RELEASE_READY:'正式交付已核准'};
export function FormalRelease({base}:{base:string}){
 const [data,setData]=useState<any>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[confirmed,setConfirmed]=useState(false);
 async function load(){setBusy(true);setError('');setConfirmed(false);try{setData(await request(`${base}/release`))}catch(e){setData(null);setError(e instanceof Error?e.message:'交付狀態讀取失敗')}finally{setBusy(false)}}
 useEffect(()=>{setData(null);void load()},[base]);
 async function act(kind:'candidate'|'approve'){
  if(busy||!confirmed)return;setBusy(true);setError('');
  try{await request(`${base}/release/${kind}`,jsonBody('POST',kind==='candidate'?{confirmed:true,qa_binding_checksum:data.qa_binding_checksum}:
   {confirmed:true,candidate_id:data.candidate.candidate_id,binding_checksum:data.approval.binding_checksum}));await load()}
  catch(e){setData(null);setConfirmed(false);setError(e instanceof Error?e.message:'交付操作失敗')}finally{setBusy(false)}
 }
 return <section aria-label="正式 Release" style={{overflowWrap:'anywhere',marginTop:24}}>
  <h4>正式 Release</h4><p>候選 ZIP 不等於交付。可攜驗證會在另設的隔離資料庫執行原始 HWF／HPL／DDL，以核准的標準答案核對；不改寫原目標、不刪表、不自動重試。</p>
  {error&&<p role="alert">{error}</p>}
  {data&&<p role="status">{labels[data.status]||'無法確認交付狀態'}</p>}
  <button disabled={busy} onClick={load}>重新核對 Release</button>
  {data?.candidate&&<p>候選 ZIP SHA-256：<code>{data.candidate.checksum}</code></p>}
  {data?.portability&&<p>可攜驗證：{data.portability.status}{data.portability.overdue?'（等待過久，需人工核對；禁止自動重跑）':''}</p>}
  {data?.status==='SDM_AND_CANDIDATE_REQUIRED'&&<div><label><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)} disabled={busy}/>確認建立候選包並要求一次隔離可攜驗證</label>
   <button disabled={busy||!confirmed} onClick={()=>act('candidate')}>保存候選 ZIP 並要求驗證</button></div>}
  {data?.status==='AWAITING_RELEASE_APPROVAL'&&<div><p>核准指紋：<code>{data.approval.binding_checksum}</code></p>
   <label><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)} disabled={busy}/>確認此版本的 QA、SDM、候選包與可攜驗證證據，同意正式交付</label>
   <button disabled={busy||!confirmed} onClick={()=>act('approve')}>核准並保存正式 Release</button></div>}
  {data?.release_ready===true&&data.release&&<div><p>正式 ZIP SHA-256：<code>{data.release.checksum}</code></p>
   <a href={`${base}/release/${data.release.release_id}/download`}>下載正式 Release ZIP</a></div>}
 </section>;
}
