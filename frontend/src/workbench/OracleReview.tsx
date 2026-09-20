import {useEffect,useState} from 'react';
import {request} from './api';

export function OracleReview({url,checksum}:{url:string;checksum:string}) {
  const [open,setOpen]=useState(false),[offset,setOffset]=useState(0),[attempt,setAttempt]=useState(0);
  const [data,setData]=useState<any>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  useEffect(()=>{
    let live=true;setData(null);setError('');if(!open)return;
    setBusy(true);
    request(url+`?offset=${offset}&limit=50`,{cache:'no-store'}).then(value=>{
      if(value.document_checksum!==checksum)throw new Error('答案指紋與版本紀錄不符');
      if(live)setData(value);
    }).catch(e=>live&&setError(e.message)).finally(()=>live&&setBusy(false));
    return()=>{live=false};
  },[open,url,checksum,offset,attempt]);
  return <div><button onClick={()=>{setData(null);setOffset(0);setOpen(value=>!value)}}>{open?'關閉答案內容':'查看答案內容'}</button>
    {open&&<section aria-label="歷史答案內容"><p>唯讀歷史內容，不代表目前規格有效或 QA 通過。關閉後清除本頁顯示；不寫入瀏覽器儲存。</p>
      {busy&&<p role="status">正在讀取答案內容…</p>}{error&&<><p role="alert">{error}</p><button onClick={()=>setAttempt(n=>n+1)}>重新讀取答案內容</button></>}
      {data&&<><p>共 {data.total_rows} 筆 · 顯示 {data.rows.length?offset+1:0}–{offset+data.rows.length} 筆</p>
        <div style={{maxWidth:'100%',overflowX:'auto'}}><table><thead><tr>{data.columns.map((column:any)=><th key={column.name}>{column.name}（{column.kind}）</th>)}</tr></thead><tbody>{data.rows.map((row:any,index:number)=><tr key={offset+index}>{data.columns.map((column:any)=><td key={column.name} style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{row[column.name]===null?<em>NULL</em>:row[column.name]===''?<em>空字串</em>:row[column.name]}</td>)}</tr>)}</tbody></table></div>
        <button disabled={busy||offset===0} onClick={()=>setOffset(n=>Math.max(0,n-50))}>上一頁答案</button><button disabled={busy||!data.has_more} onClick={()=>setOffset(n=>n+50)}>下一頁答案</button>
      </>}
    </section>}
  </div>;
}
