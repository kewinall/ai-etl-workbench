import {useState} from 'react';
import {request} from './api';

export function SdmHistory({base}:{base:string}) {
  const [items,setItems]=useState<any[]|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const load=async()=>{
    setBusy(true);setError('');setItems(null);
    try {
      const value=await request(`${base}/sdm-candidates`);
      if(!Array.isArray(value.items)||value.release_ready!==false||value.items.some((row:any)=>row.status!=='CANDIDATE_NOT_RELEASED'||row.release_ready!==false||!/^[a-f0-9-]{36}$/.test(row.sdm_id)))throw new Error('歷史文件回應不完整，請重試。');
      setItems(value.items);
    }catch(e:any){setError(e.message)}finally{setBusy(false)}
  };
  const download=async(row:any)=>{
    setBusy(true);setError('');
    try {
      const response=await fetch(`${base}/sdm-candidates/${encodeURIComponent(row.sdm_id)}/download`);
      if(!response.ok||response.headers.get('X-Content-SHA256')!==row.checksum||response.headers.get('X-SDM-Status')!=='CANDIDATE_NOT_RELEASED')throw new Error('歷史候選文件無法下載或完整性檢查未通過；紀錄仍保留。');
      const url=URL.createObjectURL(await response.blob());
      const link=document.createElement('a');link.href=url;link.download=`SDM-candidate-${row.sdm_id}.xlsx`;link.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
    }catch(e:any){setError(e.message)}finally{setBusy(false)}
  };
  return <section aria-label="SDM 候選文件歷史" style={{overflowWrap:'anywhere'}}>
    <h4>SDM 候選文件歷史</h4><p>保留本次準備版本的文件；歷史核准不代表目前仍有效，所有候選文件均非正式 Release。</p>
    <button disabled={busy} onClick={load}>{busy?'處理歷史文件中…':'載入／重新整理 SDM 歷史'}</button>
    {error&&<p role="alert">{error}</p>}
    {items?.length===0&&<p>此準備版本尚無已保存的 SDM 候選文件。</p>}
    {items&&<ul>{items.map(row=><li key={row.sdm_id}>
      <p>保存時間：{row.created_at} · {row.file_size} bytes</p>
      <details><summary>規格與文件指紋</summary><p>規格：{row.specification_checksum}</p><p>文件：{row.checksum}</p></details>
      <button disabled={busy} onClick={()=>download(row)}>下載歷史候選 Excel（非 Release）</button>
    </li>)}</ul>}
  </section>;
}
