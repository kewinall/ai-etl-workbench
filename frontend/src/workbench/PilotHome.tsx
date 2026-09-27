import {useEffect,useState} from 'react';
import {request} from './api';
import {ProjectEvaluation} from './ProjectEvaluation';

export function PilotHome({navigate}:{navigate:(path:string)=>void}) {
  const [projects,setProjects]=useState<any[]|null>(null),[selected,setSelected]=useState('');
  const [error,setError]=useState(''),[attempt,retry]=useState(0);
  useEffect(()=>{
    let live=true;setProjects(null);setError('');
    request('/api/projects').then(value=>{if(live){setProjects(value);setSelected(old=>value.some((p:any)=>p.project_id===old)?old:'')}})
      .catch(e=>{if(live)setError(e.message)});
    return()=>{live=false};
  },[attempt]);
  return <section className="panel wb-project-home" aria-label="Pilot 成果">
    <h2>Pilot 驗收與成果</h2>
    <p>目前尚無可供比較的完整 P0–P3 實測成果。初步檢查、單元測試及舊版 Task 成功紀錄不等於新版 Pilot 交付。</p>
    <p>個別案例的執行與交付證據可由下方查閱；不以靜態階段標籤取代實際紀錄，也不把歷史交付數量當成成效。</p>
    <p>模型用量紀錄與 Pilot 成效分開看待；沒有人工基準，不顯示改善率，也不提供未完成的報告匯出。</p>
    <button onClick={()=>retry(n=>n+1)}>重新讀取成果專案</button>
    {error?<p role="alert">{error}</p>:projects===null?<p role="status">正在讀取專案…</p>:<>
      <label>成果專案<select value={selected} onChange={e=>setSelected(e.target.value)}><option value="">請選擇專案</option>{projects.map(p=><option key={p.project_id} value={p.project_id}>{p.project_name}</option>)}</select></label>
      {!projects.length&&<p>尚無專案，請先至專案工作區建立。</p>}
      {selected&&<ProjectEvaluation key={selected} projectId={selected} navigate={navigate}/>}
    </>}
  </section>;
}
