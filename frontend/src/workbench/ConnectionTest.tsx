import {useState} from 'react';
import {request} from './api';
export function ConnectionTest() {
  const [busy,setBusy]=useState(false),[message,setMessage]=useState('');
  async function test(){if(busy)return;setBusy(true);setMessage('');
    try{const saved=await request('/api/settings/groups');
      const connectionId=saved.values?.data_connections_targets?.etl_qa?.connection_id;
      if(!connectionId)throw Error('尚未保存有效的資料連線');
      const data=await request(`/api/settings/connections/${encodeURIComponent(connectionId)}/test`,{method:'POST'});
      if(data.status!=='CONNECTED'||data.scope!=='SAVED_CONNECTION_SELECT_1_ONLY')throw Error('測試回應不完整');
      setMessage(`已保存連線 SELECT 1 通過（${data.duration_ms} ms）；不代表寫入權限或 ETL 驗收通過。`);
    }catch(e:any){setMessage(e.message)}finally{setBusy(false)}}
  return <section aria-label="已保存資料連線測試"><h3>測試已保存的 Vertica 連線</h3>
    <p>只執行 SELECT 1，使用已保存設定與保管庫機密；不建立資料表、不寫入資料、不改用部署預設。</p>
    <p>畫面尚未儲存的修改不會參與此測試；修改後請先保存，再重新測試。</p>
    <button disabled={busy} onClick={test}>{busy?'正在測試連線…':'測試已保存連線'}</button>
    {message&&<p role="status">{message}</p>}
  </section>;
}
