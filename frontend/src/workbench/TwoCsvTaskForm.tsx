import React, {useState} from 'react';

type Props={projectId?:string; onCreated:(task:any)=>void; onError:(message:string)=>void};
type CsvContract={version:1;encoding:string;delimiter:string;header:boolean;extra_columns:string};
const emptyContract=():CsvContract=>({version:1,encoding:'UTF-8-SIG',delimiter:',',header:true,extra_columns:'REJECT'});
async function request(url:string, init?:RequestInit){
  const response=await fetch(url,init);
  const result=await response.json();
  if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:JSON.stringify(result.detail||result));
  return result;
}

export function TwoCsvTaskForm({projectId,onCreated,onError}:Props){
  const [name,setName]=useState(''),[requirement,setRequirement]=useState('');
  const [sources,setSources]=useState<any[]>([null,null]);
  const [contracts,setContracts]=useState<CsvContract[]>([emptyContract(),emptyContract()]);
  const [keys,setKeys]=useState(['','']),[joinType,setJoinType]=useState('');
  const [confirmed,setConfirmed]=useState(false),[busy,setBusy]=useState(false);
  const [schema,setSchema]=useState('ai_sample'),[table,setTable]=useState('');
  const [uploading,setUploading]=useState<number|null>(null);
  const patchContract=(index:number,patch:Partial<CsvContract>)=>{
    setContracts(old=>old.map((value,i)=>i===index?{...value,...patch}:value));setConfirmed(false);
  };
  const upload=async(index:number,file:File)=>{
    if(!file.name.toLowerCase().endsWith('.csv')){onError('雙 CSV Join 僅接受 .csv 檔案');return;}
    setUploading(index);setConfirmed(false);
    try{
      const body=new FormData();body.append('file',file);
      const value=await request('/api/task-sources/upload',{method:'POST',body});
      if(value.source_type!=='CSV')throw new Error('上傳結果不是 CSV');
      setSources(old=>old.map((source,i)=>i===index?{...value,type:'CSV',has_actual_data:true,alias:index===0?'left_source':'right_source'}:source));
      setContracts(old=>old.map((contract,i)=>i===index?{...contract,encoding:String(value.encoding).toUpperCase(),delimiter:value.delimiter}:contract));
      setKeys(old=>old.map((key,i)=>i===index?'':key));
    }catch(error:any){onError(error.message)}finally{setUploading(null)}
  };
  const valid=!!projectId&&name.trim().length>=2&&requirement.trim().length>=5&&sources.every(Boolean)&&
    keys.every(Boolean)&&!!joinType&&confirmed&&/^[a-z_][a-z0-9_]*$/.test(schema)&&/^[a-z_][a-z0-9_]*$/.test(table);
  const submit=async()=>{
    if(!valid||busy)return;
    setBusy(true);
    try{
      const payload={name:name.trim(),requirement,category:'DW_DM',source_type:'CSV',operation:'NEW',
        source_config:{sources,csv_input_contracts_v1:{version:1,sources:{'source.0':contracts[0],'source.1':contracts[1]}}},
        target_type:'VERTICA',target_schema:schema,target_table:table,
        target_config:{stage_mode:'NORMAL',join_contract_v1:{version:1,joins:[{
          id:'join_sources',left_source:'source.0',right_source:'source.1',join_type:joinType,
          keys:[{left_column:keys[0],right_column:keys[1]}],null_key_policy:'NEVER_MATCH',
          duplicate_key_policy:'EXPAND',string_comparison:'CASE_SENSITIVE_NO_TRIM'}]}}};
      onCreated(await request(`/api/projects/${projectId}/tasks`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}));
    }catch(error:any){onError(error.message)}finally{setBusy(false)}
  };
  return <section className="panel form wb-two-csv">
    <h2>建立雙 CSV Join Task</h2>
    <p>固定兩個 CSV、單一等值 Join。建立 Task 不會執行 ETL；仍須完成需求、命名、規格與執行核准。</p>
    <label>Task 名稱<input value={name} onChange={event=>setName(event.target.value)}/></label>
    <label>需求描述<textarea rows={5} value={requirement} onChange={event=>setRequirement(event.target.value)} placeholder="說明輸出欄位、型別、篩選或彙總、寫入模式與預期結果"/></label>
    <fieldset style={{minWidth:0}} disabled={busy||uploading!==null}>
      <legend>1. 上傳並確認各來源格式</legend>
      {sources.map((source,index)=><div className="source-card" key={index}>
        <h3>{index===0?'左側':'右側'}來源 · source.{index}</h3>
        <label>{index===0?'左側 CSV':'右側 CSV'}<input type="file" accept=".csv" onChange={event=>event.target.files?.[0]&&upload(index,event.target.files[0])}/></label>
        {uploading===index&&<p role="status">上傳與解析中…</p>}
        {source&&<><p style={{overflowWrap:'anywhere'}}>{source.original_name} · {source.fields.length} 欄</p>
          <ul>{source.fields.map((field:any)=><li key={field.name}>{field.name} · {field.type}</li>)}</ul>
          <label>{index===0?'左側編碼':'右側編碼'}<select aria-label={index===0?'左側編碼':'右側編碼'} value={contracts[index].encoding} onChange={event=>patchContract(index,{encoding:event.target.value})}>
            {['UTF-8','UTF-8-SIG','BIG5'].map(value=><option key={value}>{value}</option>)}
          </select></label>
          <label>{index===0?'左側分隔符':'右側分隔符'}<select aria-label={index===0?'左側分隔符':'右側分隔符'} value={contracts[index].delimiter} onChange={event=>patchContract(index,{delimiter:event.target.value})}>
            {[['逗號',','],['直線','|'],['分號',';'],['Tab','\t']].map(([label,value])=><option key={label} value={value}>{label}</option>)}
          </select></label>
          <p>首列為欄位名稱；多餘欄位拒絕匯入。格式變更後，執行前仍會重新驗證檔案。</p>
        </>}
      </div>)}
      <h3>2. 明確指定 Join</h3>
      <label>Join 類型<select aria-label="Join 類型" value={joinType} onChange={event=>{setJoinType(event.target.value);setConfirmed(false)}}>
        <option value="">請選擇，不自動推測</option><option value="LEFT">LEFT · 保留所有左側資料</option><option value="INNER">INNER · 只保留配對資料</option>
      </select></label>
      {keys.map((key,index)=><label key={index}>{index===0?'左側鍵值':'右側鍵值'}<select aria-label={index===0?'左側鍵值':'右側鍵值'} value={key} onChange={event=>{setKeys(old=>old.map((value,i)=>i===index?event.target.value:value));setConfirmed(false)}}>
        <option value="">請選擇欄位</option>{(sources[index]?.fields||[]).map((field:any)=><option key={field.name} value={field.name}>{field.name}</option>)}
      </select></label>)}
      <p>空鍵值不匹配；重複鍵展開所有組合（可能增加筆數）；字串區分大小寫且不自動去除空白。</p>
      <label><input type="checkbox" checked={confirmed} onChange={event=>setConfirmed(event.target.checked)}/>我已確認左右來源、檔案格式、Join 類型、鍵值與上述三項規則</label>
    </fieldset>
    <h3>3. Vertica 目標</h3>
    <label>Vertica Schema<input value={schema} onChange={event=>setSchema(event.target.value)}/></label>
    <label>Vertica Table<input value={table} onChange={event=>setTable(event.target.value)}/></label>
    <p>請使用小寫英文、數字與底線。受控 Pilot 僅允許平台登錄的測試範圍；填寫名稱不代表授權刪除既有資料。</p>
    {!projectId&&<p role="alert">請先從專案內進入建立 Task。</p>}
    <button className="primary" disabled={!valid||busy||uploading!==null} onClick={submit}>{busy?'建立中…':'建立雙 CSV Task'}</button>
  </section>;
}
