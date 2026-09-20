import {useEffect,useState} from 'react';
import {request,jsonBody} from './api';

export function SAApproval({base}:{base:string}) {
  const [data,setData]=useState<any>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[confirmed,setConfirmed]=useState(false);
  const load=async()=>{setBusy(true);setError('');setData(null);setConfirmed(false);
    try {setData(await request(base+'/sa-approval'))} catch {setError('無法核對 SA 交接狀態，請重試；目前不可核准。')} finally {setBusy(false)}};
  useEffect(()=>{let live=true;request(base+'/sa-approval').then(v=>live&&setData(v)).catch(()=>live&&setError('無法核對 SA 交接狀態，請重新核對。'));return()=>{live=false}},[base]);
  return <section aria-label="SA 人工交接">
    <h5>SA 建議人工確認</h5>
    <p>這是需求審查的交接，不是 ETL 執行、QA 或 Release 核准。</p>
    {error&&<p role="alert">{error}</p>}
    {data?.status==='NOT_ELIGIBLE'&&<p>目前尚無可交接的 SA 結果；需完成審查、補正缺口並保持版本一致。</p>}
    {data?.status==='STALE_APPROVAL'&&<p role="alert">歷史核准已失效；原紀錄保留，不能沿用到新需求或設定。</p>}
    {data?.status==='APPROVED_CURRENT'&&<p role="status">此版 SA 建議已人工核准。{data.developer_authorized?'可進行 Developer 設計；模型用量需另外同意。':'目前不可再次派發 Developer。'}</p>}
    {data?.status==='AWAITING_CONFIRMATION'&&<>
      <details><summary>待確認版本指紋</summary><p style={{overflowWrap:'anywhere'}}>{data.binding.checksum}</p></details>
      <label><input type="checkbox" checked={confirmed} disabled={busy} onChange={e=>setConfirmed(e.target.checked)}/>我已檢視 SA 建議與原需求，確認此版本可交給 Developer</label>
      <button disabled={busy||!confirmed} onClick={async()=>{
        setBusy(true);setError('');
        try {await request(base+'/sa-approval',jsonBody('POST',{confirmed:true,binding_checksum:data.binding.checksum}));setData(await request(base+'/sa-approval'));setConfirmed(false)}
        catch {setData(null);setConfirmed(false);setError('核准未完成或版本已變更，請重新核對；未授權執行 ETL。')}
        finally {setBusy(false)}
      }}>確認 SA 建議並交接</button>
    </>}
    <button disabled={busy} onClick={load}>重新核對 SA 交接</button>
  </section>;
}
