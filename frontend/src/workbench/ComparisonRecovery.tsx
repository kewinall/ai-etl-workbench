import {useEffect,useState} from 'react';
import {jsonBody,request} from './api';
import {useWorkflowRefresh,useOperation} from './useWorkflowRefresh';
import {ExecutionReconciliation} from './ExecutionReconciliation';

export function ComparisonRecovery({base}:{base:string}) {
  const url=base+'/comparison-recovery';
  const op=useOperation('comparison_recovery');
  const readOnly=!op.enabled;
  const [attempt,setAttempt]=useState(0);
  const [data,setData]=useState<any>(null),[consent,setConsent]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  useWorkflowRefresh(base,()=>setAttempt(n=>n+1),busy||consent);
  useEffect(()=>{let live=true;request(url).then(value=>{if(live){setData(value);setError('')}}).catch(e=>{if(live){setData(null);setError(e.message)}});return()=>{live=false}},[url,attempt]);
  async function refresh(){setBusy(true);setConsent(false);setError('');try{setData(await request(url))}catch(e:any){setData(null);setError(e.message)}finally{setBusy(false)}}
  async function save(){if(busy||readOnly||!consent)return;setBusy(true);setError('');try{
    setData(await request(url,jsonBody('POST',{confirmed:consent,binding_checksum:data.binding_checksum})));setConsent(false);
  }catch(e:any){setData(null);setConsent(false);setError(e.message)}finally{setBusy(false)}}
  if(data?.status==='NOT_ELIGIBLE')return null;
  return <section aria-label="只重新比對結果"><h5>只重新比對結果</h5>
    <p>僅適用於 Hop 已確定完成、結果比對後處理失敗的版本。使用原已核准查詢重新讀取目標，不會啟動 Hop、建表、清空或再次寫入；原失敗紀錄仍保留。</p>
    <button disabled={busy} onClick={refresh}>重新核對比對恢復狀態</button>
    {error&&<p role="alert">{error}。請先重新核對狀態；不會自動重送。</p>}
    {data?.status==='AWAITING_CONFIRMATION'&&<>
      {!data.enabled?<p>部署尚未啟用受控 Worker。</p>:<>
        <label><input type="checkbox" disabled={readOnly||busy} checked={consent} onChange={e=>setConsent(e.target.checked)}/>我同意只重新讀取並比對原結果，不重跑 ETL，也不視為 QA 或 Release 核准</label>
        <button disabled={readOnly||busy||!consent} onClick={save}>授權重新比對（不重跑 ETL）</button>
      </>}
    </>}
    {data?.status==='QUEUED'&&<p role="status">已排入結果比對，等待 Worker 領取；不會重跑 ETL。</p>}
    {data?.status==='CLAIMED'&&<p role="status">Worker 已領取比對。若長時間未回報，需核對 Worker 與紀錄；不自動重試。</p>}
    {data?.status==='COMPLETED'&&<p role="status">{data.outcome_code==='RESULT_MATCH_QA_REQUIRED'?'結果比對一致':'結果比對不一致'}；已保存新證據，仍需 QA 審查與交付核准。原 Hop 派發失敗紀錄未改寫。</p>}
    {data?.status==='FAILED'&&<p role="alert">本次比對恢復未成功，已保留紀錄；沒有重跑 ETL，不能宣告 QA 或交付通過。</p>}
    {data?.outcome_code==='RESULT_NULL_NOT_ALLOWED'&&<p role="alert">實際結果含 NULL，但已核准標準答案禁止 NULL。請查看原答案內容；已執行版本不可事後改答案，修正需建立新版並使用新目標。</p>}
    {data?.status==='FAILED'&&<ExecutionReconciliation base={base} onSaved={async()=>{await refresh()}}/>}
  </section>;
}
