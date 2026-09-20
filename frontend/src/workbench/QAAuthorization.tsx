import {useEffect,useState} from 'react';
import {jsonBody,request} from './api';

export function QAAuthorization({taskId,runId}:{taskId:string;runId:string}) {
  const base=`/api/tasks/${encodeURIComponent(taskId)}/runs/${runId}/qa-authorization`;
  const [data,setData]=useState<any>(null),[consent,setConsent]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  useEffect(()=>{let live=true;request(base).then(value=>{if(live)setData(value)}).catch(e=>{if(live)setError(e.message)});return()=>{live=false}},[base]);
  async function refresh(){setBusy(true);setData(null);setConsent(false);setError('');try{setData(await request(base))}catch(e:any){setError(e.message)}finally{setBusy(false)}}
  async function authorize(){
    setBusy(true);setError('');
    try{
      await request(base,jsonBody('POST',{confirmed:consent,reassess_invocation_id:data.reassess_invocation_id??null,...Object.fromEntries(['comparison_id','context_checksum','prompt_checksum','schema_checksum','model'].map(key=>[key,data[key]]))}));
      setData(await request(base));setConsent(false);
    }catch(e:any){setData(null);setConsent(false);setError(e.message)}finally{setBusy(false)}
  }
  return <section aria-label="QA 模型呼叫授權"><h4>QA 模型呼叫授權</h4>
    <p>模型將對照需求、執行規格、節點與已保存的 Hop／結果證據；此授權不等於 QA 通過或交付核准。</p>
    <button disabled={busy} onClick={refresh}>重新核對 QA 派發條件</button>
    {error&&<p role="alert">{error}。未重送模型請求，請重新核對。</p>}
    {data?.invocation&&!data.reassess_invocation_id?<p>已有 QA 呼叫紀錄（{data.invocation.status}），不會重送。請重新讀取下方審查結果。</p>
      :data&&!data.eligible?<p>尚不符合派發條件：需完成 Hop、保存受控來源比對證據，並使用有效的 Copilot 路由。</p>
      :data&&!data.dispatch_enabled?<p>部署尚未啟用 QA 派發，目前不會呼叫模型。</p>
      :data&&<>
        {data.reassess_invocation_id&&<p>前次 NEEDS_REVIEW 將永久保留。審查指引已更新，可另行同意一次複核；不重跑 Hop、不沿用 QA 核准、不保證 PASS。</p>}
        <p>模型：{data.model}。使用本機登入額度，1 次 CLI、不自動重試或換模型、禁止工具操作；無法保證輸出 Token 硬上限。本機 QA Worker 必須另行執行。</p>
        <label><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/>我同意此版本 QA 單次模型呼叫與用量</label>
        <button disabled={busy||!consent} onClick={authorize}>{data.reassess_invocation_id?'授權一次 QA 複核':'授權 QA 證據審查'}</button>
      </>}
  </section>;
}
