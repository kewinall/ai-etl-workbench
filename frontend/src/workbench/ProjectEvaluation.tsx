import {useEffect,useState} from 'react';
import {request} from './api';

export function ProjectEvaluation({projectId,navigate}:{projectId:string;navigate:(path:string)=>void}) {
  const [data,setData]=useState<any>(null),[error,setError]=useState(''),[attempt,retry]=useState(0);
  useEffect(()=>{
    let live=true;setData(null);setError('');
    request(`/api/projects/${encodeURIComponent(projectId)}/evaluation`).then(value=>{
      if(value.project_id!==projectId||value.basis!=='ALL_PERSISTED_RUNS')throw Error('評估資料不屬於此專案');
      if(live)setData(value);
    }).catch(e=>{if(live)setError(e.message)});
    return()=>{live=false};
  },[projectId,attempt]);
  return <section className="panel" aria-label="專案 Pilot 評估">
    <h3>Pilot 案例與證據</h3><p>保留所有準備版本，包括失敗與取消；這是證據清單，不是已完成的成效比較。</p>
    <button onClick={()=>retry(n=>n+1)}>重新讀取評估證據</button>
    {error?<p role="alert">{error}</p>:!data?<p role="status">正在讀取評估證據…</p>:<>
      <ul>{data.limitations.map((text:string)=><li key={text}>{text}</li>)}</ul>
      {!data.cases.length?<p>此專案尚無 Task，尚未納入任何比較案例。</p>:data.cases.map((item:any)=><article className="wb-record" key={`${item.task_id}:${item.run_id||'none'}`}>
        <h4>{item.name}</h4><p>{item.task_id} · {item.run_id?`版本 ${item.run_id}`:'尚無準備版本'}</p>
        <p>控制狀態：{item.state||'NO_RUN'} · {item.phase||'未開始'} · {item.outcome_code||'尚無結果'}</p>
        <p>保存的歷史交付紀錄：{item.historical_release_count}（非目前可下載判定）</p>
        <button onClick={()=>navigate(`/projects/${projectId}/tasks/${encodeURIComponent(item.task_id)}/execution`)}>查看 Task 執行與 QA 證據</button>
      </article>)}
    </>}
  </section>;
}
