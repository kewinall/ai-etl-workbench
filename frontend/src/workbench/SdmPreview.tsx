import {useEffect,useState} from 'react';
import {request,jsonBody} from './api';
import {JoinSummary} from './JoinSummary';

export function SdmPreview({url,specificationChecksum}:{url:string;specificationChecksum:string}) {
  const [attempt,setAttempt]=useState(0),[data,setData]=useState<any>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [saving,setSaving]=useState(false),[saved,setSaved]=useState<any>(null);
  const createCandidate=async()=>{
    setSaving(true);setError('');setSaved(null);
    try {
      const value=await request(url.replace(/sdm-preview$/,'sdm-candidate'),jsonBody('POST',{content_checksum:specificationChecksum}));
      if(value.specification_checksum!==specificationChecksum||value.status!=='CANDIDATE_NOT_RELEASED'||value.qa_passed!==false||value.release_ready!==false||!/^[a-f0-9-]{36}$/.test(value.sdm_id))throw new Error('候選文件版本或狀態不符，無法下載。');
      setSaved(value);
    } catch(e:any){setError(e.message)} finally{setSaving(false)}
  };
  const download=async()=>{
    setSaving(true);setError('');
    try {
      const base=url.substring(0,url.indexOf('/specifications/'));
      const response=await fetch(`${base}/sdm-candidates/${encodeURIComponent(saved.sdm_id)}/download`);
      if(!response.ok)throw new Error('候選文件無法下載，請重新產生並確認版本或檔案完整性。');
      if(response.headers.get('X-SDM-Status')!=='CANDIDATE_NOT_RELEASED'||response.headers.get('X-Content-SHA256')!==saved.checksum)throw new Error('下載文件識別不符。');
      const objectUrl=URL.createObjectURL(await response.blob());
      const link=document.createElement('a');link.href=objectUrl;link.download=`SDM-candidate-${saved.sdm_id}.xlsx`;link.click();
      setTimeout(()=>URL.revokeObjectURL(objectUrl),1000);
    } catch(e:any){setError(e.message)} finally{setSaving(false)}
  };
  useEffect(()=>{
    let live=true;if(!attempt)return;
    setBusy(true);setData(null);setError('');setSaved(null);
    request(url).then(value=>{
      if(value.document?.specification_checksum!==specificationChecksum||value.status!=='SDM_CANDIDATE_NOT_RELEASED')throw new Error('SDM 與目前規格版本不符');
      const document=value.document;
      if(![1,2].includes(document.version)||document.document_type!=='SDM_CANDIDATE'||value.qa_passed!==false||value.release_ready!==false||document.filter_logic!=='ALL'||document.filter_null_policy!=='EXCLUDE_UNKNOWN'||document.target?.write_mode!=='APPEND'||(document.aggregation&&document.aggregation.null_policy!=='SQL_NULLS'))throw new Error('SDM 政策或文件版本不受支援，請重新核對規格。');
      if(document.version===2&&(!Array.isArray(document.source_refs)||document.source_refs.join(',')!=='source.0,source.1'||!Array.isArray(document.joins)||document.joins.length!==1))throw new Error('SDM 雙來源或 Join 規則不完整。');
      if(live)setData(value);
    }).catch(e=>live&&setError(e.message)).finally(()=>live&&setBusy(false));
    return()=>{live=false};
  },[url,specificationChecksum,attempt]);
  const labels:Record<string,string>={DIRECT:'直接對應',GROUP_KEY:'分組欄位',SUM:'加總',COUNT_ROWS:'計算資料筆數',COUNT_NON_NULL:'計算非空值筆數'};
  const operators:Record<string,string>={EQ:'等於',NE:'不等於',LT:'小於',LE:'小於或等於',GT:'大於',GE:'大於或等於',IS_NULL:'是 NULL',IS_NOT_NULL:'不是 NULL'};
  return <section aria-label="SDM 欄位對照預覽" style={{overflowWrap:'anywhere'}}>
    <button disabled={busy||saving} onClick={()=>setAttempt(n=>n+1)}>{busy?'讀取 SDM 中…':'預覽 SDM 欄位對照'}</button>
    {error&&<p role="alert">{error}</p>}
    {data&&<><h5>SDM 候選內容（尚不可交付）</h5><p>顯示此規格的轉換規則、輸出欄位及來源關係；{saved?'已取得候選 Excel':'尚未產生 Excel'}，且不代表執行、QA 或 Release 通過。</p>
      <button disabled={busy||saving} onClick={createCandidate}>{saving?'處理候選文件中…':'產生／取得 SDM 候選 Excel'}</button>
      {saved&&<><p role="status">候選 Excel 已保存；尚未通過 QA，不可作為正式交付。</p><button disabled={busy||saving} onClick={download}>下載 SDM 候選 Excel（非 Release）</button></>}
      <section aria-label="SDM 轉換規則">
        <h6>來源與目標</h6>
        <p>來源識別：{data.document.version===2?data.document.source_refs.join('、'):data.document.source_ref}</p>
        <JoinSummary joins={data.document.joins}/>
        <p>目標表：{data.document.target.schema}.{data.document.target.table}</p>
        <p>寫入模式：{data.document.target.write_mode==='APPEND'?'附加資料（APPEND）':data.document.target.write_mode}</p>
        <h6>篩選條件</h6>
        {data.document.filters.length?<>
          <p>所有條件皆須成立（ALL）；條件結果為未知值的資料會排除（EXCLUDE_UNKNOWN）。</p>
          <ol>{data.document.filters.map((filter:any,index:number)=><li key={index}>
            <code>{filter.column}</code> {operators[filter.operator]||filter.operator}
            {filter.constant&&<>：<code style={{whiteSpace:'pre-wrap'}}>{filter.constant.value===''?'空字串（長度 0）':String(filter.constant.value)}</code>（{filter.constant.type}）</>}
          </li>)}</ol>
        </>:<p>無篩選條件，保留全部來源資料。</p>}
        <h6>分組與聚合</h6>
        {data.document.aggregation?<><p>分組欄位：{data.document.aggregation.group_by.length?data.document.aggregation.group_by.join('、'):'無分組欄位（整體聚合）'}</p><p>空值處理：SQL_NULLS；各聚合輸出與來源列於下表。</p></>:<p>不進行聚合，依輸出順序直接對應欄位。</p>}
      </section>
      <div style={{maxWidth:'100%',overflowX:'auto'}}><table><thead><tr><th>順序</th><th>輸出欄位</th><th>型別</th><th>轉換方式</th><th>來源欄位</th></tr></thead><tbody>{data.document.mappings.map((mapping:any)=><tr key={mapping.target_column}><td>{mapping.position}</td><td>{mapping.target_column}</td><td>{mapping.target_type}</td><td>{labels[mapping.operation]||mapping.operation}</td><td>{mapping.source_columns.length?mapping.source_columns.map((source:any)=>`${data.document.version===2?source.source_ref+'.':''}${source.original_name} → ${source.stream_name}`).join('、'):'整筆資料計數（不對應單一欄位）'}</td></tr>)}</tbody></table></div>
      <details><summary>SDM 版本指紋</summary><p>{data.checksum}</p><p>命名指紋：{data.document.naming.checksum}</p><p>規格指紋：{data.document.specification_checksum}</p></details>
    </>}
  </section>;
}
