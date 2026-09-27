import {useState} from 'react';
import {request} from './api';

const fields:Record<string,[string,string][]>={
  ai_provider_model_strategy:[['default_profile','預設 AI Profile']],
  data_connections_targets:[['etl_qa.connection_id','Connection ID'],['etl_qa.host','Host'],['etl_qa.port','Port'],['etl_qa.database','Database'],['etl_qa.user','User'],['etl_qa.tlsmode','TLS 模式']],
  validation_release_policy:[['sample_rows','範例資料筆數'],['require_naming_contract','必須確認 Naming Contract']],
  execution_tool_paths:[['hop_run_path','Apache Hop 執行檔'],['hop_project_path','Hop 專案目錄'],['runtime_temp_path','暫存工作目錄']],
};
function display(value:any,path:string){
  const result=path.split('.').reduce((v,key)=>v?.[key],value);
  if(result===null||result===undefined||result==='')return '未設定';
  if(typeof result==='boolean')return result?'是':'否';
  return typeof result==='string'||typeof result==='number'?String(result):'非預期格式';
}
export function SettingsComparison({group,draft,disabled,onAdopt}:{group:string;draft:any;disabled:boolean;onAdopt:(value:any,version:string)=>void}){
  const [latest,setLatest]=useState<any>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const read=async()=>{
    if(busy||disabled)return;
    setBusy(true);setError('');
    try{
      const result=await request('/api/settings/groups');
      if(!result.values?.[group]||!result.versions?.[group])throw new Error('設定或版本回應不完整，草稿未變更');
      setLatest({value:result.values[group],version:result.versions[group]});
    }catch(e:any){setError(e.message)}finally{setBusy(false)}
  };
  if(!fields[group])return null;
  return <section aria-label="設定分組版本比較">
    <button type="button" disabled={disabled||busy} onClick={read}>比較此分類草稿與最新設定</button>
    {error&&<p role="alert">{error}</p>}
    {latest&&<>
      <p>只讀比較，不會寫入或自動合併。僅列出可編輯的一般欄位，不讀取密鑰。</p>
      <div className="settings-fields">{fields[group].map(([path,label])=><div key={path} style={{minWidth:0,overflowWrap:'anywhere'}}>
        <b>{label}</b><p>草稿：{display(draft,path)}</p><p>最新：{display(latest.value,path)}</p>
      </div>)}</div>
      <button type="button" disabled={disabled||busy} onClick={()=>setLatest(null)}>保留此分類草稿並關閉比較</button>
      <button type="button" disabled={disabled||busy} onClick={()=>{onAdopt(latest.value,latest.version);setLatest(null)}}>捨棄此分類草稿，採用所示最新版本</button>
      <p>其他分類草稿不變；若伺服器其後再次更新，下一次儲存仍會拒絕過期版本。</p>
    </>}
  </section>;
}
