import {useEffect,useRef,useState} from 'react';
import {request,jsonBody} from './api';

export function ExecutionReconciliation({base,onSaved}:{base:string;onSaved:()=>Promise<void>}) {
  const [data,setData]=useState<any>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [engine,setEngine]=useState(false),[target,setTarget]=useState(false),[confirmed,setConfirmed]=useState(false);
  const [rows,setRows]=useState(''),[hash,setHash]=useState(''),[reading,setReading]=useState(false);
  const sequence=useRef(0);
  useEffect(()=>{let live=true;request(base+'/reconciliation').then(v=>live&&setData(v)).catch(()=>live&&setError('無法讀取人工核對狀態，請重新載入版本。'));return()=>{live=false;sequence.current++}},[base]);
  if(data?.status==='NOT_ELIGIBLE')return null;
  const rowCount=Number(rows);
  return <section aria-label="執行結果人工核對">
    <h4>人工核對與結案</h4>
    {error&&<p role="alert">{error}</p>}
    {!data&&!error&&<p>正在讀取核對狀態…</p>}
    {data?.status==='CLOSED_WITHOUT_RETRY'?<>
      <p role="status">已人工結案，未重跑、未核准 QA 或交付。</p>
      <p>核對時目標筆數：{data.observed_row_count}；原執行結果：{data.original_outcome}</p>
      <details><summary>核對證據指紋</summary><p style={{overflowWrap:'anywhere'}}>{data.evidence_sha256}</p><p>核對時間：{new Date(data.created_at).toLocaleString()}</p></details>
    </>:data?.status==='AWAITING_RECONCILIATION'&&<>
      <p>先確認 Hop 已停止，再核對此版本的目標資料。平台不會代替你停止引擎、刪除資料或重跑；結案不代表寫入已回復。</p>
      <label><input type="checkbox" checked={engine} disabled={busy} onChange={e=>setEngine(e.target.checked)}/>我已確認本次 Hop 程序停止</label>
      <label><input type="checkbox" checked={target} disabled={busy} onChange={e=>setTarget(e.target.checked)}/>我已核對本次目標與寫入範圍，並保留查詢證據</label>
      <label>核對時目標筆數<input type="number" min="0" step="1" value={rows} disabled={busy} onChange={e=>setRows(e.target.value)}/></label>
      <label>選擇核對證據檔案<input type="file" disabled={busy} onChange={async e=>{
        const file=e.target.files?.[0],id=++sequence.current;setHash('');setError('');setReading(false);
        if(!file)return;
        if(!file.size||file.size>5*1024*1024){setError('請選擇 1 byte 至 5 MB 的核對證據檔案。');return}
        setReading(true);
        try {const bytes=await crypto.subtle.digest('SHA-256',await file.arrayBuffer());if(sequence.current===id)setHash(Array.from(new Uint8Array(bytes)).map(v=>v.toString(16).padStart(2,'0')).join(''))}
        catch {if(sequence.current===id)setError('無法計算證據指紋，請重新選擇檔案。')}
        finally {if(sequence.current===id)setReading(false)}
      }}/></label>
      <p>檔案留在本機，不會上傳；平台只保存 SHA-256 指紋與筆數。請自行保留原始證據，供日後核對。</p>
      {hash&&<details><summary>已計算證據指紋</summary><p style={{overflowWrap:'anywhere'}}>{hash}</p></details>}
      <label><input type="checkbox" checked={confirmed} disabled={busy} onChange={e=>setConfirmed(e.target.checked)}/>我確認只結束此次失敗／未知版本，不重跑，也不宣告成功</label>
      <button disabled={busy||reading||!engine||!target||!confirmed||!hash||rows===''||!Number.isSafeInteger(rowCount)||rowCount<0} onClick={async()=>{
        setBusy(true);setError('');
        try {await request(base+'/reconciliation',jsonBody('POST',{binding_checksum:data.binding.checksum,evidence_sha256:hash,observed_row_count:rowCount,engine_stopped:engine,target_checked:target,confirmed}));setData(await request(base+'/reconciliation'));await onSaved()}
        catch {setData(null);setConfirmed(false);setError('核對未完成或版本已變更，請重新載入版本確認保存狀態；不要直接重跑。')}
        finally {setBusy(false)}
      }}>{busy?'保存中…':'保存人工核對並結案（不重跑）'}</button>
    </>}
  </section>;
}
