import {useEffect,useState} from 'react';
import {request,jsonBody} from './api';
import {useDraftGuard} from './useDraftGuard';
import {useWorkflowRefresh} from './useWorkflowRefresh';

export function NamingConfirmation({taskId,runId,historical,editable,sourceOrder}:{taskId:string;runId?:string;historical?:boolean;editable:boolean;sourceOrder?:any}){
 const base=`/api/tasks/${encodeURIComponent(taskId)}/naming-contract`;
 const [columns,setColumns]=useState<any[]>([]),[saved,setSaved]=useState<any>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[confirmed,setConfirmed]=useState(false),[editing,setEditing]=useState(false);
 const readBase=historical&&runId?`/api/tasks/${encodeURIComponent(taskId)}/runs/${runId}/specifications`:base;
 const load=async()=>{const v=await request(readBase);const contract=historical?v.items[0]?.bound_naming:v.contract;setSaved(contract);setColumns(contract?.contract_json?.columns||[])};
 useEffect(()=>{let live=true;request(readBase).then(v=>{if(live){const contract=historical?v.items[0]?.bound_naming:v.contract;setSaved(contract);setColumns(contract?.contract_json?.columns||[])}}).catch(e=>{if(live)setError(e.message)});return()=>{live=false}},[readBase,historical]);
 useDraftGuard(editing,busy,setError);
 useWorkflowRefresh(`/api/tasks/${encodeURIComponent(taskId)}/runs/${runId||''}`,load,editing||busy);
 async function act(work:()=>Promise<void>){setBusy(true);setError('');try{await work()}catch(e){setError(e instanceof Error?e.message:'命名操作失敗')}finally{setBusy(false)}}
 const update=(i:number,key:string,value:string)=>{setColumns(columns.map((c,n)=>n===i?{...c,[key]:value}:c));setConfirmed(false)};
 return <section aria-label="欄位命名確認" style={{overflowWrap:'anywhere'}}><h4>欄位命名確認</h4>
  <p>來源欄位與聚合輸出共用同一版本。來源型別不可縮減精度；聚合來源代號填入 $metric.計算ID，例如 $metric.total。保存新版本會使下游舊設計失效，不覆寫歷史。</p>
  {sourceOrder && !sourceOrder.invalid && <p>來源序號是系統產生欄位，不在 CSV 原始欄位中。請確認 $source_order.source.0 → {sourceOrder.ordinal_column}，型別 BIGINT。</p>}
  {error&&<p role="alert">{error}</p>}
  {historical&&<p>顯示此 Run 規格當時綁定的命名契約；未保存規格時沒有可確認的歷史綁定，不顯示目前 Task 命名。</p>}
  {saved&&<p>已保存命名第 {saved.version} 版 · {saved.status} · <code>{saved.checksum}</code></p>}
  {!editing&&<><button disabled={busy||!editable} onClick={()=>act(async()=>{const v=await request(`${base}/suggest`,{method:'POST'});setColumns(v.contract.columns);setEditing(true);setConfirmed(false)})}>取得來源命名建議</button>
   {saved&&<button disabled={busy||!editable} onClick={()=>{setColumns(saved.contract_json.columns);setEditing(true);setConfirmed(false)}}>修改並建立命名新版</button>}
   {columns.map((c,i)=><p key={i}>{c.source_name} → {c.english_name} · {c.vertica_type}</p>)}</>}
  {editing&&<><div>{columns.map((c,i)=><fieldset key={i}><legend>命名欄位 {i+1}</legend>
   <label>來源或聚合代號<input aria-label={`命名來源 ${i+1}`} value={c.source_name} onChange={e=>update(i,'source_name',e.target.value)}/></label>
   <label>英文名稱<input aria-label={`命名英文 ${i+1}`} value={c.english_name} onChange={e=>update(i,'english_name',e.target.value)}/></label>
   <label>Vertica 型別<input aria-label={`命名型別 ${i+1}`} value={c.vertica_type} onChange={e=>update(i,'vertica_type',e.target.value)}/></label>
   <button disabled={busy} onClick={()=>{setColumns(columns.filter((_,n)=>n!==i));setConfirmed(false)}}>移除命名欄位 {i+1}</button></fieldset>)}</div>
   <button disabled={busy||columns.length>=200} onClick={()=>{setColumns([...columns,{source_name:'$metric.',english_name:'',vertica_type:'BIGINT',confidence:1,reason:'operator_confirmed'}]);setConfirmed(false)}}>新增聚合輸出命名</button>
   {sourceOrder && !sourceOrder.invalid && <button disabled={busy||columns.length>=200||columns.some(c=>c.source_name==='$source_order.source.0')} onClick={()=>{setColumns([...columns,{source_name:'$source_order.source.0',english_name:sourceOrder.ordinal_column,vertica_type:'BIGINT',confidence:1,reason:'operator_confirmed'}]);setConfirmed(false)}}>加入來源序號命名</button>}
   <label><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>我已核對原名、英文名稱與型別</label>
   <button disabled={busy||!confirmed||!columns.length||!editable} onClick={()=>act(async()=>{const v=await request(`${base}/confirm`,jsonBody('POST',{columns:columns.map(c=>({...c,reason:'operator_confirmed'}))}));setSaved(v);setColumns(v.contract_json.columns);setEditing(false);setConfirmed(false)})}>確認並保存命名版本</button>
   <button disabled={busy} onClick={()=>{setColumns(saved?.contract_json?.columns||[]);setEditing(false)}}>取消命名修改</button></>}
 </section>;
}
