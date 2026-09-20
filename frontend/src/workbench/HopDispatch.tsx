import {useEffect,useState} from 'react';
import {jsonBody,request} from './api';

export function HopDispatch({taskId,runId}:{taskId:string;runId:string}) {
  const base=`/api/tasks/${encodeURIComponent(taskId)}/runs/${runId}/hop-dispatch`;
  const [data,setData]=useState<any>(null),[consent,setConsent]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  useEffect(()=>{let live=true;request(base).then(value=>{if(live)setData(value)}).catch(e=>{if(live)setError(e.message)});return()=>{live=false}},[base]);
  async function refresh(){setBusy(true);setData(null);setConsent(false);setError('');try{setData(await request(base))}catch(e:any){setError(e.message)}finally{setBusy(false)}}
  async function dispatch(){setBusy(true);setError('');try{
    await request(base,jsonBody('POST',{confirmed:consent,specification_id:data.offer.specification_id,binding_checksum:data.offer.binding_checksum}));
    setData(await request(base));setConsent(false);
  }catch(e:any){setData(null);setConsent(false);setError(e.message)}finally{setBusy(false)}}
  return <section aria-label="Hop 單次執行"><h4>Hop 單次執行</h4>
    <p>需完成 SA／Developer、規格及標準答案核准。授權後由 Worker 新建專用測試表、執行一次 Hop 並保存結果比對；不是 QA 或交付核准。</p>
    <button disabled={busy} onClick={refresh}>重新核對 Hop 執行條件</button>
    {error&&<p role="alert">{error}。請核對執行紀錄，不要直接重送。</p>}
    {data?.request?<><p>工作狀態：{data.request.status}；結果：{data.request.outcome_code||'尚未回報'}。不自動重跑。</p>
      {data.request.overdue&&<p role="alert">Worker 超過預期時間未結案，執行結果不明；請人工核對程序與目標表，不能重新派發此版本。</p>}</>
      :data&&!data.offer?<p>{data.blocked_reason}</p>
      :data&&<><p>目標：{data.offer.target_schema}.{data.offer.target_table}。只允許新建；表已存在即停止，絕不 DROP 或清空。</p>
        <details><summary>檢視即將執行的建表 DDL</summary><pre>{data.offer.ddl}</pre></details>
        {!data.dispatch_enabled?<p>部署尚未啟用 Hop 執行，不會寫入資料庫。</p>:<>
          <label><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/>我已核對規格、標準答案及 DDL，同意新建此測試表並執行一次 Hop 寫入；失敗不自動重跑</label>
          <button disabled={busy||!consent} onClick={dispatch}>授權並排入 Hop 執行</button>
        </>}
      </>}
  </section>;
}
