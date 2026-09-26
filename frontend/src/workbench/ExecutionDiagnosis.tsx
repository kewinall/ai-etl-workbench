import {useEffect,useState} from 'react';
import {request} from './api';

export function ExecutionDiagnosis({base}:{base:string}) {
  const [data,setData]=useState<any>(null),[error,setError]=useState('');
  useEffect(()=>{let live=true;setData(null);setError('');
    request(base+'/diagnosis').then(v=>{if(live)setData(v)}).catch(()=>{if(live)setError('無法取得已綁定的診斷證據；請重新載入，勿直接重跑。')});
    return()=>{live=false};
  },[base]);
  return <section aria-label="失敗診斷證據"><h4>失敗診斷（程式規則，非 AI）</h4>
    {error&&<p role="alert">{error}</p>}
    {!data&&!error&&<p>正在核對日誌指紋…</p>}
    {data?.status==='LOG_EVIDENCE_UNAVAILABLE'&&<p>沒有完整可綁定的日誌，無法判定原因。請先核對引擎及資料庫。</p>}
    {data?.status==='EVIDENCE_REVIEW_REQUIRED'&&<>
      <p>{data.limitation}</p>
      {!data.findings.length&&<p>目前沒有可辨識的錯誤訊號；不得將此視為成功。</p>}
      <ul>{data.findings.map((f:any)=><li key={f.code}>{f.message}（日誌行號：{f.line_numbers.join('、')}）</li>)}</ul>
      <ol>{data.next_steps.map((s:string)=><li key={s}>{s}</li>)}</ol>
      <details><summary>日誌證據指紋</summary><p style={{overflowWrap:'anywhere'}}>{data.log_checksum}</p></details>
    </>}
  </section>;
}
