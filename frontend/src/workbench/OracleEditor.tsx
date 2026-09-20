import {useEffect,useState} from 'react';
import {request,jsonBody} from './api';
import {oracleDocument,type OracleColumn,type OracleCell} from './oracleDocument';

export function OracleEditor({base,onHistory}:{base:string;onHistory:(items:any[])=>void}) {
  const [context,setContext]=useState<any>(null),[columns,setColumns]=useState<OracleColumn[]>([]);
  const [rows,setRows]=useState<OracleCell[][]>([]),[dirty,setDirty]=useState(false);
  const [busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[error,setError]=useState('');
  const [message,setMessage]=useState(''),[saved,setSaved]=useState<any>(null),[confirmed,setConfirmed]=useState(false),[attempt,setAttempt]=useState(0);
  useEffect(()=>{
    let live=true;setLoading(true);setError('');
    request(base+'/oracle-editor-context').then(data=>{if(live){setContext(data);setColumns(data.columns)}})
      .catch(e=>live&&setError(e.message)).finally(()=>live&&setLoading(false));
    return()=>{live=false};
  },[base,attempt]);
  useEffect(()=>{
    if(!dirty&&!busy)return;
    const leave=(event:Event)=>{
      if(event.defaultPrevented)return;
      if(busy){event.preventDefault();window.alert('答案操作正在處理，請等待結果後再離開。');return}
      if(!window.confirm('標準答案尚未保存，確定放棄修改？'))event.preventDefault();
    };
    const unload=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue=''};
    window.addEventListener('workbench:before-navigate',leave);window.addEventListener('beforeunload',unload);
    return()=>{window.removeEventListener('workbench:before-navigate',leave);window.removeEventListener('beforeunload',unload)};
  },[dirty,busy]);
  const changed=()=>{setDirty(true);setSaved(null);setConfirmed(false);setMessage('');setError('')};
  const save=async()=>{
    if(busy||!context)return;setBusy(true);setError('');setMessage('');setSaved(null);setConfirmed(false);
    try{
      const document=oracleDocument(context,columns,rows);
      const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(document));
      const checksum=Array.from(new Uint8Array(digest)).map(b=>b.toString(16).padStart(2,'0')).join('');
      const result=await request(base+'/oracles',jsonBody('POST',{document}));
      if(result.document_checksum!==checksum)throw new Error('保存結果與目前答案指紋不符');
      const history=await request(base+'/oracles');
      const latest=history.items[0];
      if(latest?.oracle_id!==result.oracle_id||latest.document_checksum!==checksum)throw new Error('答案版本已變更，無法確認目前答案為最新版本');
      onHistory(history.items);setSaved(latest);setDirty(false);setMessage('答案已保存並核對版本；尚未執行 QA。');
    }catch(e:any){setError('保存或回讀未完成：'+e.message+'。內容保留，請核對後再操作。')}
    finally{setBusy(false)}
  };
  const approve=async()=>{
    if(busy||!saved||!confirmed||dirty)return;setBusy(true);setError('');setMessage('');
    try{
      await request(base+'/oracles/'+saved.oracle_id+'/approve',jsonBody('POST',{document_checksum:saved.document_checksum,confirmed:true}));
      const history=await request(base+'/oracles');const latest=history.items[0];
      if(latest?.oracle_id!==saved.oracle_id||latest.document_checksum!==saved.document_checksum||!latest.approval_recorded)throw new Error('無法回讀相同版本的核准');
      onHistory(history.items);setSaved(latest);setConfirmed(false);setMessage('此答案版本的人工核准已保存；不代表 QA 通過或可交付。');
    }catch(e:any){setError('核准或回讀未完成：'+e.message)}finally{setBusy(false)}
  };
  return <section aria-label="標準答案輸入"><h4>建立標準答案版本</h4>
    <p>依已核准規格輸入預期結果。筆數為零代表預期沒有任何輸出；空文字與 NULL 不同。小數與大整數會保留精度。</p>
    {loading&&<p role="status">正在檢查規格與欄位…</p>}
    {error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
    {!context&&!loading&&<button onClick={()=>setAttempt(n=>n+1)}>重新檢查答案欄位</button>}
    {context&&<><fieldset disabled={busy} style={{minWidth:0,border:0,padding:0}}><legend>答案欄位與資料（{rows.length} 筆）</legend>
      <p>NULL 政策由你明確指定；新增資料列後請逐欄填寫。保存會建立不可變版本。</p>
      {columns.map((column,i)=><label key={column.name} style={{display:'block'}}><input type="checkbox" checked={column.nullable} onChange={e=>{changed();setColumns(old=>old.map((c,j)=>j===i?{...c,nullable:e.target.checked}:c));if(!e.target.checked)setRows(old=>old.map(row=>row.map((cell,j)=>j===i?{...cell,isNull:false}:cell)))}}/>{column.name}（{column.kind}）允許 NULL</label>)}
      <div style={{maxWidth:'100%',overflowX:'auto'}}><table><thead><tr><th>筆次</th>{columns.map(c=><th key={c.name}>{c.name}</th>)}<th>操作</th></tr></thead><tbody>{rows.map((row,index)=><tr key={index}><td>{index+1}</td>{columns.map((column,i)=><td key={column.name}>
        {column.kind==='BOOLEAN'?<select aria-label={`第 ${index+1} 筆 ${column.name}`} disabled={row[i].isNull} value={row[i].value} onChange={e=>{changed();setRows(old=>old.map((r,n)=>n===index?r.map((cell,j)=>j===i?{...cell,value:e.target.value}:cell):r))}}><option value="">請選擇</option><option value="true">true</option><option value="false">false</option></select>:<input aria-label={`第 ${index+1} 筆 ${column.name}`} disabled={row[i].isNull} value={row[i].value} onChange={e=>{changed();setRows(old=>old.map((r,n)=>n===index?r.map((cell,j)=>j===i?{...cell,value:e.target.value}:cell):r))}}/>}
        {column.nullable&&<label><input type="checkbox" aria-label={`第 ${index+1} 筆 ${column.name} NULL`} checked={row[i].isNull} onChange={e=>{changed();setRows(old=>old.map((r,n)=>n===index?r.map((cell,j)=>j===i?{...cell,isNull:e.target.checked}:cell):r))}}/>NULL</label>}
      </td>)}<td><button onClick={()=>{changed();setRows(old=>old.filter((_,n)=>n!==index))}}>刪除第 {index+1} 筆</button></td></tr>)}</tbody></table></div>
      <button disabled={rows.length>=context.max_rows} onClick={()=>{changed();setRows(old=>[...old,columns.map(()=>({value:'',isNull:false}))])}}>新增答案資料列</button>
      <button onClick={save}>{busy?'處理中…':'保存答案版本'}</button>
      {saved&&<><p>目前表格對應答案第 {saved.version} 版 · {saved.document_checksum}</p>{!saved.approval_recorded&&<><label><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>我已確認上方答案內容與版本，核准供後續 QA 比對</label><button disabled={!confirmed||dirty} onClick={approve}>核准此答案版本</button></>}</>}
    </fieldset><p>歷史答案可在上方唯讀查閱；本表單只能核准本次保存並核對的版本。修改任一欄位後須重新保存。</p></>}
  </section>;
}
