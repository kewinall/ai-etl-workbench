import {useEffect,useState} from 'react';
import {request} from './api';

export function ComparisonHistory({taskId,runId}:{taskId:string;runId:string}) {
  const [items,setItems]=useState<any[]>([]),[busy,setBusy]=useState(true),[error,setError]=useState(''),[attempt,setAttempt]=useState(0);
  useEffect(()=>{
    let live=true;setItems([]);setBusy(true);setError('');
    request(`/api/tasks/${encodeURIComponent(taskId)}/runs/${runId}/comparisons`).then(data=>{if(live)setItems(data.items)})
      .catch(e=>live&&setError(e.message)).finally(()=>live&&setBusy(false));
    return()=>{live=false};
  },[taskId,runId,attempt]);
  return <section aria-label="結果比對證據" style={{overflowWrap:'anywhere'}}><h3>結果比對證據</h3>
    <p>對應上方選擇的準備版本。請分別檢視結果差異與來源核對狀態；比對一致不等於 QA 通過，也不能據此交付。</p>
    <button disabled={busy} onClick={()=>setAttempt(n=>n+1)}>重新讀取比對證據</button>
    {busy&&<p role="status">正在讀取比對紀錄…</p>}{error&&<p role="alert">無法讀取比對證據：{error}</p>}
    {!busy&&!error&&!items.length&&<p>此準備版本尚無保存的結果比對；不是零差異或 QA 通過。</p>}
    {items.map(item=>{const e=item.evidence;return <article className="wb-record" key={item.comparison_id}>
      <h4>{e.status==='MATCH'?'比對一致（非正式 QA）':e.status==='MISMATCH'?'發現結果差異':'未知比對狀態'}</h4>
      <p>{item.provenance?.status==='BOUND_PLATFORM_TARGET'?'來源已核對（平台管理目標）':'來源尚未驗證'} · 保存時間：{new Date(item.created_at).toLocaleString()}</p>
      {item.provenance?.status==='BOUND_PLATFORM_TARGET'&&<section aria-label="結果來源核對"><p>已核對本次 Run 的目標歸屬、執行前空表紀錄、指定版本連線及核准查詢。此為平台內來源證據，不是正式 QA 核准，也不保證外部管理者未修改資料。</p><dl><dt>空表確認時間</dt><dd>{new Date(item.provenance.empty_checked_at).toLocaleString()}</dd><dt>來源核對時間</dt><dd>{new Date(item.provenance.checked_at).toLocaleString()}</dd><dt>核准查詢指紋</dt><dd>{item.provenance.query_checksum}</dd></dl></section>}
      <dl><dt>預期筆數</dt><dd>{e.expected_count}</dd><dt>實際讀取筆數</dt><dd>{e.actual_count}</dd><dt>缺少的結果筆數</dt><dd>{e.missing_count}</dd><dt>多出的結果筆數</dt><dd>{e.unexpected_count}</dd></dl>
      <p>使用精確多重集合比對：忽略列順序，但保留重複筆數、型別與 NULL 差異。</p>
      <details><summary>追溯版本與指紋</summary><dl><dt>證據 ID</dt><dd>{item.comparison_id}</dd><dt>證據指紋</dt><dd>{item.checksum}</dd><dt>答案版本 ID</dt><dd>{e.oracle_id}</dd><dt>答案文件指紋</dt><dd>{e.oracle_document_checksum}</dd><dt>執行授權指紋</dt><dd>{e.execution_binding_checksum}</dd><dt>Hop 完成事件</dt><dd>{e.hop_event_id}</dd><dt>Hop 日誌指紋</dt><dd>{e.hop_log_checksum}</dd></dl></details>
    </article>})}
  </section>;
}
