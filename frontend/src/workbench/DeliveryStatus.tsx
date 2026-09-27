import {useEffect,useState} from 'react';
import {request} from './api';

const labels: Record<string,string> = {
  PREREQUISITES_REQUIRED:'尚需完成角色協作、Hop 與 QA 核准',
  SDM_AND_CANDIDATE_REQUIRED:'待建立 SDM 與候選包',
  PORTABILITY_REQUIRED:'待可攜驗證',
  EVIDENCE_CHANGED:'證據已變更，交付阻擋',
  AWAITING_RELEASE_APPROVAL:'驗證完成，待交付核准',
};

/** Read-only current evidence check; never infer delivery from a legacy Task status. */
export function DeliveryStatus({taskId,runId,onOpen}:{taskId:string;runId:string;onOpen:()=>void}) {
  const [data,setData]=useState<any>(null),[error,setError]=useState('');
  useEffect(()=>{
    let live=true; setData(null);setError('');
    request(`/api/tasks/${encodeURIComponent(taskId)}/runs/${encodeURIComponent(runId)}/release`)
      .then(value=>{if(live)setData(value)})
      .catch(e=>{if(live)setError(e.message)});
    return()=>{live=false};
  },[taskId,runId]);
  const ready=data?.status==='RELEASE_READY'&&data?.release_ready===true&&!!data?.release;
  return <section aria-label="最新版本交付狀態">
    <h4>最新版本交付</h4>
    {error?<p role="alert">無法確認交付狀態：{error}。請到交付頁重新核對。</p>
      :!data?<p role="status">正在核對交付證據…</p>
      :<p role="status">{ready?'正式交付已核准':labels[data.status]||'交付狀態尚未確認'}</p>}
    <p>交付核准與控制流程狀態分開保存；不以舊版 Task 狀態判定是否已交付。</p>
    <button onClick={onOpen}>查看交付證據與下載</button>
  </section>;
}
