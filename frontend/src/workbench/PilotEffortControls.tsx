import {useRef,useState} from 'react';
import {jsonBody,request} from './api';

export function PilotEffortControls({data,reload}:{data:any;reload:()=>Promise<void>}){
  const endpoint=`/api/projects/${data.project_id}/pilot-cohorts/${data.cohort_id}/cases/${encodeURIComponent(data.case_key)}/effort`;
  const storageKey=`effort-pending:${endpoint}`;
  const [actor,setActor]=useState(''),[mode,setMode]=useState('WORKBENCH');
  const [confirmed,setConfirmed]=useState(false),[activeOnly,setActiveOnly]=useState(false);
  const [message,setMessage]=useState(''),[busy,setBusy]=useState(false);
  const latch=useRef(false);
  const [pending,setPending]=useState<any>(()=>{
    try{return JSON.parse(sessionStorage.getItem(storageKey)||'null')}catch{return {unreadable:true}}
  });
  const active=data.recovery?data.events.find((e:any)=>e.action==='START'&&e.session_id===data.recovery.session_id):null;
  const expired=data.recovery?.status==='EXPIRED_REQUIRES_ABANDON';
  async function send(body:any){
    if(latch.current)return;
    latch.current=true;setBusy(true);setMessage('');
    try{
      if(!body||body.unreadable||body.expected_protocol_checksum!==data.protocol_checksum)throw Error('待確認請求版本不符，請先讀取並核對伺服器紀錄。');
      sessionStorage.setItem(storageKey,JSON.stringify(body));setPending(body);
      const saved=await request(endpoint,jsonBody('POST',body));
      if(saved.request_key!==body.request_key||saved.cohort_id!==data.cohort_id||saved.case_key!==data.case_key||
        !['START','STOP','ABANDON'].includes(saved.action))throw Error('保存回應無法核對，請用原請求重試。');
      sessionStorage.removeItem(storageKey);setPending(null);setConfirmed(false);setActiveOnly(false);
      await reload();
    }catch(e:any){setMessage(e.message)}finally{latch.current=false;setBusy(false)}
  }
  function submit(action:string){
    if(!confirmed||pending)return;
    const selectedActor=action==='START'?actor:active?.actor;
    if(!selectedActor||action==='STOP'&&(!activeOnly||expired))return;
    void send({request_key:crypto.randomUUID(),action,actor:selectedActor,
      mode:action==='START'?mode:active.mode,session_id:action==='START'?null:active.session_id,
      expected_protocol_checksum:data.protocol_checksum,confirmed:true,
      human_attested:selectedActor==='HUMAN_SELF_REPORTED'});
  }
  return <fieldset disabled={busy} aria-label="計時操作">
    <legend>記錄短操作區間</legend>
    <p>每段最多 120 秒。等待、離開頁面或無法確認全程操作時請放棄；目前不會自動追蹤操作或扣除閒置。</p>
    <p>真人來源僅為自行聲明，未驗證身分；功能測試及代理操作不列入真人工時。</p>
    {pending?<>
      <p role="status">有待確認請求，先重試原請求並回讀；不要另開區間。</p>
      <button disabled={pending.unreadable} onClick={()=>void send(pending)}>重試原計時請求</button>
      <button onClick={()=>{sessionStorage.removeItem(storageKey);setPending(null);void reload()}}>清除本機待確認請求並回讀</button>
      <p>清除只移除本機重試資料，不會關閉或刪除伺服器計時。</p>
    </>:<>
      {!data.recovery&&<>
        <label>操作者來源<select value={actor} onChange={e=>{setActor(e.target.value);setConfirmed(false)}}>
          <option value="">請明確選擇</option><option value="HUMAN_SELF_REPORTED">本人操作（自行聲明）</option>
          <option value="DELEGATED_AGENT">代理操作</option><option value="FUNCTIONAL_TEST">功能測試</option>
        </select></label>
        <label>量測模式<select value={mode} onChange={e=>{setMode(e.target.value);setConfirmed(false)}}>
          <option value="WORKBENCH">工作台操作</option><option value="MANUAL_BASELINE">人工基準</option>
        </select></label>
      </>}
      <label><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>我確認操作者來源及區間；本人操作為自行聲明</label>
      {data.recovery?<>
        <label><input type="checkbox" checked={activeOnly} onChange={e=>setActiveOnly(e.target.checked)}/>本段全程主動操作，未含等待或閒置</label>
        <button disabled={!active||!confirmed||!activeOnly||expired} onClick={()=>submit('STOP')}>結束並保存區間</button>
        <button disabled={!active||!confirmed} onClick={()=>submit('ABANDON')}>放棄本區間</button>
      </>:<button disabled={!actor||!confirmed||data.other_case_open} onClick={()=>submit('START')}>開始操作區間</button>}
    </>}
    {message&&<p role="alert">{message}</p>}
  </fieldset>;
}
