import {useEffect,useState} from 'react';
import {request,jsonBody} from './api';
import {useWorkflowReadOnly,useWorkflowRefresh} from './useWorkflowRefresh';

export function ExecutionReconciliation({base,onSaved,preparation=false}:{base:string;onSaved:()=>Promise<void>;preparation?:boolean}) {
  const endpoint=base+(preparation?'/hop-preparation-reconciliation':'/reconciliation');
  const readOnly=useWorkflowReadOnly();
  const [data,setData]=useState<any>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [confirmed,setConfirmed]=useState(false),[rows,setRows]=useState(''),[targetExists,setTargetExists]=useState('');
  const [attempt,setAttempt]=useState(0);
  useWorkflowRefresh(base,()=>setAttempt(n=>n+1),busy||confirmed||rows!==''||targetExists!=='');
  useEffect(()=>{let live=true;request(endpoint).then(v=>{if(live){setData(v);setError('')}}).catch(()=>live&&setError('目前無法核對結案狀態，請重新讀取後再操作。'));return()=>{live=false}},[endpoint,attempt]);
  if(data?.status==='NOT_ELIGIBLE')return null;
  const rowCount=Number(rows),rowsRequired=!preparation||targetExists==='yes';
  const invalidRows=rowsRequired&&(rows===''||!Number.isSafeInteger(rowCount)||rowCount<0);
  return <section aria-label={preparation?'Hop 準備失聯人工核對':'執行結果人工核對'}>
    <h4>{preparation?'結束失聯的準備工作':'結束此次執行，保留結果'}</h4>
    {error&&<><p role="alert">{error} 不會自動重送。</p><button disabled={busy} onClick={()=>{setConfirmed(false);setAttempt(n=>n+1)}}>重新讀取結案狀態</button></>}
    {!data&&!error&&<p role="status">正在讀取結案狀態…</p>}
    {data?.status==='CLOSED_WITHOUT_RETRY'?<>
      <p role="status">已人工結案，未重跑、未核准 QA 或交付。</p>
      <p>{preparation&&data.target_exists===false?'核對時目標不存在（不是零筆）':`核對時目標筆數：${data.observed_row_count}`}</p>
      <p>此版已結案，原結果已保留。需要修正時，按上方「建立修正版」；新版將沿用原需求，再使用新目標與正確標準答案重新確認。</p>
    </>:data?.status==='AWAITING_RECONCILIATION'&&<>
      <p>先確認本次執行{preparation?'與 Worker':''}已停止，再填入目標筆數並確認結案。結案後可建立修正版，原結果會保留。</p>
      {preparation&&<label>目標表是否存在<select value={targetExists} disabled={busy||readOnly} onChange={e=>{setTargetExists(e.target.value);setRows('');setConfirmed(false)}}><option value="">請選擇</option><option value="no">不存在</option><option value="yes">存在</option></select></label>}
      {rowsRequired&&<label>核對時目標筆數<input type="number" min="0" step="1" value={rows} disabled={busy||readOnly} onChange={e=>{setRows(e.target.value);setConfirmed(false)}}/></label>}
      <label><input type="checkbox" checked={confirmed} disabled={busy||readOnly||invalidRows||(preparation&&!targetExists)} onChange={e=>setConfirmed(e.target.checked)}/>我已確認本次執行{preparation?'與 Worker':''}停止，目標核對結果正確，同意結案並保留原結果</label>
      <p>這次操作只結案，不會重跑、刪除資料或核准交付。無需準備證據檔案。</p>
      <button disabled={busy||readOnly||!!error||!confirmed||invalidRows||(preparation&&!targetExists)} onClick={async()=>{
        if(busy||readOnly||!confirmed||error)return;
        setBusy(true);setError('');
        try {await request(endpoint,jsonBody('POST',{binding_checksum:data.binding.checksum,observed_row_count:rowsRequired?rowCount:null,...(preparation?{target_exists:targetExists==='yes'}:{}),engine_stopped:confirmed,target_checked:confirmed,confirmed}));setData(await request(endpoint));setConfirmed(false);await onSaved()}
        catch {setConfirmed(false);setError('結案結果尚未確認；輸入已保留，請先重新讀取伺服器狀態。')}
        finally {setBusy(false)}
      }}>{busy?'結案中…':'確認結案，保留結果'}</button>
    </>}
  </section>;
}
