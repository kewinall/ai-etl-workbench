import {useEffect,useState} from 'react';
import {request} from './api';
export function ControlDatabaseStatus() {
  const [status,setStatus]=useState(''),[error,setError]=useState(''),[attempt,retry]=useState(0);
  useEffect(()=>{let live=true;setStatus('');setError('');
    request('/api/ready').then(data=>{
      if(data.status!=='ready')throw Error('平台就緒回應不完整');
      if(live)setStatus('PostgreSQL 連線與必要平台資料表檢查通過');
    }).catch(()=>{if(live)setError('無法確認平台資料庫就緒；請檢查 API、部署連線與 migration。')});
    return()=>{live=false};
  },[attempt]);
  return <section className="panel" aria-label="平台控制資料庫狀態">
    <h3>平台 PostgreSQL（部署管理、唯讀）</h3>
    {error?<p role="alert">{error}</p>:<p role="status">{status||'正在檢查平台就緒狀態…'}</p>}
    <p>僅驗證平台連線與必要資料表，不代表備份、還原或 ETL 通過。此頁不切換控制資料庫，也不顯示部署機密。</p>
    <p>變更方式：先備份控制資料與加密主金鑰，停止 Worker，調整部署 DATABASE_URL，執行 migration 並重新驗證；不可把 Vertica 連線欄位當成平台資料庫設定。</p>
    <button onClick={()=>retry(n=>n+1)}>重新檢查平台資料庫</button>
  </section>;
}
