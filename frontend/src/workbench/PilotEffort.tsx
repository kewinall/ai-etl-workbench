import {useEffect,useRef,useState} from 'react';
import {request} from './api';

export function PilotEffort({projectId,cohortId,caseKey}:{projectId:string;cohortId:string;caseKey:string}){
  const [data,setData]=useState<any>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const generation=useRef(0);
  useEffect(()=>{generation.current++;setData(null);setError('');setBusy(false);return()=>{generation.current++}},[projectId,cohortId,caseKey]);
  async function load(){
    const current=++generation.current;setBusy(true);setError('');setData(null);
    try{
      const value=await request(`/api/projects/${projectId}/pilot-cohorts/${cohortId}/cases/${encodeURIComponent(caseKey)}/effort`);
      if(value.project_id!==projectId||value.cohort_id!==cohortId||value.case_key!==caseKey||
        !Array.isArray(value.events)||value.comparison_ready!==false||!value.summary?.totals)
        throw Error('計時證據回應不完整或案例不符；不顯示為零工時。');
      if(current===generation.current)setData(value);
    }catch(e:any){if(current===generation.current)setError(e.message)}
    finally{if(current===generation.current)setBusy(false)}
  }
  return <section aria-label={`案例 ${caseKey} 操作時間`}>
    <h5>操作時間紀錄</h5>
    <p>區間小計不等於完整案例工時；等待模型與 ETL 的時間不可冒充人工操作。</p>
    <button disabled={busy} onClick={load}>{busy?'讀取中…':'查看／重新讀取計時紀錄'}</button>
    {error&&<p role="alert">{error}</p>}
    {data&&<>
      <p>真人計時：{data.human_recording_enabled?'請依確認流程操作':'尚未啟用'}；成效比較：尚未完成。</p>
      {(['WORKBENCH','MANUAL_BASELINE'] as const).map(mode=>{
        const metric=data.summary.totals[mode], seconds=metric?.recorded_human_seconds;
        return <p key={mode}>{mode==='WORKBENCH'?'工作台真人操作':'人工基準'}：
          {typeof seconds==='number'&&Number.isFinite(seconds)&&seconds>=0?`${seconds.toFixed(1)} 秒（僅已記錄區間）`:'尚未量測'}
        </p>;
      })}
      <p>代理／功能測試區間：{data.summary.excluded_nonhuman_sessions} 段（不列入真人工時）。放棄區間：{data.summary.abandoned_sessions} 段。</p>
      {data.recovery&&<p role="status">{data.recovery.status==='EXPIRED_REQUIRES_ABANDON'
        ?'未結束區間已逾時，必須明確放棄；不計入工時。'
        :'有未結束區間，須明確核對後關閉；不會自動續計。'}</p>}
      {data.other_case_open&&<p role="status">另一案例有未結束計時，關閉前不能開始新區間。</p>}
      {!data.events.length?<p>尚無計時事件；不代表零工時。</p>:<ol>
        {data.events.map((event:any)=><li key={event.sequence}>
          #{event.sequence} · {event.action==='START'?'開始':event.action==='STOP'?'結束':'放棄'} ·
          {event.actor==='FUNCTIONAL_TEST'?'功能測試':event.actor==='DELEGATED_AGENT'?'代理操作':'真人來源待核對'} · {event.recorded_at}
        </li>)}
      </ol>}
      <p>此區目前僅供讀取與復原檢視，尚未提供開始／結束操作，不會修改已保存紀錄。</p>
    </>}
  </section>;
}
