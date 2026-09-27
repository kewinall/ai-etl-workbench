import {useEffect,useRef,useState} from 'react';
import {request} from './api';

export function PilotMeasurements({projectId,navigate}:{projectId:string;navigate:(path:string)=>void}) {
  const [data,setData]=useState<any>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const generation=useRef(0),latch=useRef(false);
  useEffect(()=>{generation.current++;setData(null);setError('');return()=>{generation.current++}},[projectId]);
  const refresh=async()=>{
    if(latch.current)return;
    latch.current=true;setBusy(true);setError('');const captured=generation.current;
    try{
      const value=await request(`/api/projects/${encodeURIComponent(projectId)}/pilot-measurements`);
      if(value.project_id!==projectId||value.basis!=='FROZEN_COHORT_CURRENT_DELIVERY_V1'||!Array.isArray(value.cohorts))throw Error('量測資料範圍不符');
      if(captured===generation.current)setData(value);
    }catch(e:any){if(captured===generation.current){setData(null);setError(e.message)}}
    finally{latch.current=false;setBusy(false)}
  };
  return <section className="panel" aria-label="正式案例量測">
    <h3>正式案例量測</h3>
    <p>重新檢查各案例最新版的交付證據，不執行模型或 ETL。交付數不等於情境驗收率；人工工時與改善率仍待實測。</p>
    <button disabled={busy} onClick={refresh}>{busy?'正在核對交付證據…':'重新量測正式案例'}</button>
    <p><a href={`/api/projects/${encodeURIComponent(projectId)}/pilot-report`} target="_blank" rel="noopener noreferrer">開啟可列印成果報告</a>（重新核對證據；可用瀏覽器列印或另存 HTML）</p>
    {error&&<p role="alert">{error}</p>}
    {data&&<><p>核對區間：{new Date(data.checked_from).toLocaleString()} ～ {new Date(data.checked_until).toLocaleString()}</p>
      <ul>{data.limitations.map((v:string)=><li key={v}>{v}</li>)}</ul>
      {!data.cohorts.length&&<p>尚無正式登錄集合，不計算通過率。</p>}
      {data.cohorts.map((c:any)=><article key={c.cohort_id}>
        <h4>{c.name}</h4><p>目前可交付：{c.release_ready_count} / {c.denominator}；無法確認：{c.unverified_count}。準備版本 {c.attempt_count}，補正版本 {c.revision_count}。</p>
        <p>符合凍結情境證據：{c.scenario_evidence_matched_count??'尚未核對'} / {c.denominator}（包含來源指紋、固定答案、前置攔截／失敗修正與目前交付；不代表工時改善）。</p>
        <p>首次通過率、人工操作工時、人工基準、改善率與成本：尚無完整量測。</p>
        <section aria-label="操作時間覆蓋">
          <h5>已記錄操作區間（不是完整案例工時）</h5>
          {c.effort?.status==='RECORDED_INTERVALS_ONLY'?<>
            <p>真人來源為自行聲明、未驗證身分；有區間紀錄不等於全案已量測，不能據此推算改善率。</p>
            {(['WORKBENCH','MANUAL_BASELINE'] as const).map(mode=>{
              const m=c.effort.modes[mode];return <p key={mode}>
                {mode==='WORKBENCH'?'工作台操作':'人工基準'}：{m.recorded_seconds===null?'尚未量測':`已記錄 ${m.recorded_seconds.toFixed(1)} 秒`}；
                有區間紀錄 {m.cases_with_recorded_intervals} / {c.effort.denominator} 案，未記錄 {m.cases_without_recorded_intervals} 案。
              </p>;
            })}
            <p>排除代理／功能測試 {c.effort.excluded_nonhuman_sessions} 段，放棄 {c.effort.abandoned_sessions} 段。
              {c.effort.has_open_session?'仍有未結束區間，不計入小計。':''}</p>
          </>:<p>計時覆蓋暫時無法核對，不代表零工時。</p>}
        </section>
        {c.usage&&<section aria-label="模型用量覆蓋">
          <h5>模型用量（含所有版本）</h5>
          <ul>{c.usage.limitations.map((v:string)=><li key={v}>{v}</li>)}</ul>
          {c.usage.groups.map((g:any)=><article key={`${g.provider}:${g.model}`} className="wb-record">
            <p>{g.provider} / {g.model}：{g.journal_invocations} 筆紀錄，其中 {g.nonaccepted_invocations} 筆非已接受結果；供應商標示部分回報 {g.provider_partial_records} 筆。</p>
            {Object.entries({input_tokens:'輸入 Token',output_tokens:'輸出 Token',total_tokens:'總 Token',ai_credits:'AI credits',premium_requests:'Premium requests',duration_ms:'請求處理耗時（毫秒）'}).map(([key,label])=>{
              const m=g.metrics[key];return <p key={key}>{label}：{m.reported_sum===null?'未回報':`已回報合計 ${m.reported_sum}`}；覆蓋 {m.reported_invocations} / {g.journal_invocations} 筆，缺 {m.missing_invocations} 筆。{m.complete_sum===null?'完整總量不可用。':''}</p>
            })}
          </article>)}
          {!c.usage.groups.length&&<p>尚無模型用量紀錄，不推定為零消耗。</p>}
        </section>}
        {c.cases.map((row:any)=><article className="wb-record" key={row.case_key}>
          <h5>{row.title}</h5><p>{row.status} · 準備版本 {row.attempt_count} · 補正 {row.revision_count}</p>
          {row.scenario_evidence&&<p>情境證據：{row.scenario_evidence.status}；來源指紋{row.scenario_evidence.source_verified?'已核對':'尚未核對'}、固定答案{row.scenario_evidence.frozen_oracle_verified?'已核對':'尚未核對'}、前置情境{row.scenario_evidence.precondition?'有綁定證據':'尚缺證據'}。</p>}
          <p>首版建立至交付總經過時間：{row.elapsed_to_delivery_seconds===null?'尚無可用交付時間':`${Math.round(row.elapsed_to_delivery_seconds)} 秒（含等待，非人工工時）`}</p>
          {c.usage?.cases?.[row.task_id]&&<p>本案模型紀錄（含舊版）：{c.usage.cases[row.task_id].journal_invocations} 筆；成本尚無可用費率。</p>}
          {row.task_id&&row.run_id&&<button onClick={()=>navigate(`/projects/${projectId}/tasks/${encodeURIComponent(row.task_id)}/execution/${encodeURIComponent(row.run_id)}`)}>查看量測版本證據</button>}
        </article>)}
      </article>)}
    </>}
  </section>;
}
