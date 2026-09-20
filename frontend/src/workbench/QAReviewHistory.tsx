import {useEffect,useState} from 'react';
import {request} from './api';
import {QAApproval} from './QAApproval';
import {QAAuthorization} from './QAAuthorization';

const labels:Record<string,string>={QA_RESERVED:'已保存審查意圖（不代表模型已完成）',QA_OUTCOME_UNKNOWN:'結果不確定，需人工核對',VALIDATED_NOT_APPROVED:'建議已通過格式驗證，尚未核准',STALE_RESULT_NEEDS_REVIEW:'歷史版本建議，需重新核對'};
const checks:Record<string,string>={specification:'規格與命名',static_validation:'流程靜態檢查',hop_execution:'Hop 執行',result_comparison:'標準答案比對',result_source:'結果來源'};
export function QAReviewHistory({taskId,runId}:{taskId:string;runId:string}) {
  const [data,setData]=useState<any>(null),[busy,setBusy]=useState(true),[error,setError]=useState(''),[attempt,setAttempt]=useState(0);
  useEffect(()=>{
    let live=true;setData(null);setError('');setBusy(true);
    request(`/api/tasks/${encodeURIComponent(taskId)}/runs/${runId}/qa-review`)
      .then(value=>{if(live)setData(value)}).catch(e=>{if(live)setError(e.message)})
      .finally(()=>{if(live)setBusy(false)});
    return()=>{live=false};
  },[taskId,runId,attempt]);
  const item=data?.invocation;
  const history=data?.history??(item?[item]:[]);
  return <section aria-label="QA 審查紀錄" style={{overflowWrap:'anywhere'}}><h3>QA 審查紀錄</h3>
    <p>QA 為 AI 角色建議；下列程式證據檢查不等於 AI 審查。模型建議與人工核准分別呈現，Release 仍需獨立驗證。</p>
    <QAAuthorization key={`${taskId}:${runId}`} taskId={taskId} runId={runId}/>
    <button disabled={busy} onClick={()=>setAttempt(n=>n+1)}>重新讀取 QA 審查</button>
    {busy&&<p role="status">正在讀取 QA 審查…</p>}{error&&<p role="alert">無法讀取 QA 審查：{error}</p>}
    {!busy&&!error&&data&&!item&&<p>此 Run 尚無 QA 模型審查紀錄；不是 QA 通過。</p>}
    {history.map((item:any,index:number)=><article className="wb-record" key={item.invocation_id}><h4>{index===0?'最新審查':'保留的歷史審查'} · {labels[item.status]||'未知審查狀態'}</h4>
      <p>審查指引版本：{item.prompt_version}{item.reassesses_invocation_id?`；複核自 ${item.reassesses_invocation_id}`:''}</p>
      {data.matches_current===false&&<p>上游已變更，這份紀錄僅供歷史追溯。</p>}
      <dl><dt>模型</dt><dd>{item.model}</dd><dt>保存時間</dt><dd>{new Date(item.created_at).toLocaleString()}</dd><dt>模型耗時</dt><dd>{item.duration_ms==null?'未提供':`${item.duration_ms} ms`}</dd><dt>Token 用量</dt><dd>{item.usage?.total_tokens??'未提供'}</dd></dl>
      {item.review&&<><h5>QA 建議：{item.review.status}</h5><p>{item.review.summary}</p><ul>{item.review.issues.map((issue:any,index:number)=><li key={index}>{issue.message}（引用：{issue.evidence_ids.join('、')}）</li>)}</ul></>}
      {item.status==='QA_OUTCOME_UNKNOWN'&&<p>不能判定模型是否完成，不會自動重送請求。</p>}
      <h5>當時的程式證據</h5><ul>{item.context.evidence.map((check:any)=><li key={check.id}><b>{checks[check.id]||check.id}：{check.status}</b><p>{check.summary}</p></li>)}</ul>
      {item.context.semantics && <details><summary>當時的語意審查依據</summary>
        <p>原始需求：{item.context.semantics.requirement}</p>
        <p>寫入模式：{item.context.semantics.specification.write_mode}；輸出欄位：{item.context.semantics.specification.output_columns.join('、')}</p>
        <p>篩選條件 {item.context.semantics.specification.filters.length} 項；{item.context.semantics.specification.aggregation ? `聚合 ${item.context.semantics.specification.aggregation.metrics.length} 項` : '沒有聚合'}。完整版本仍可在需求與規格頁查閱。</p>
        <ul>{item.context.semantics.nodes.map((node:any)=><li key={node.id}>{node.id} · 程式元件 {node.component}</li>)}</ul>
        {item.context.semantics.execution_details&&<>
          <p>CSV：{item.context.semantics.execution_details.csv_input_contract.encoding}；標題列：{item.context.semantics.execution_details.csv_input_contract.header?'有':'無'}；額外欄位：{item.context.semantics.execution_details.csv_input_contract.extra_columns}。整批結構檢查在 Hop 前執行；本證據重新核對相同 checksum 的來源，不重跑 ETL。</p>
          <p>來源完整掃描：{item.context.semantics.execution_details.csv_structure_validation.records_checked} 筆。</p>
          <ul>{Object.entries(item.context.semantics.execution_details.output_types).map(([name,type])=><li key={name}>{name} · {String(type)}</li>)}</ul>
          <ul>{item.context.semantics.execution_details.compiler_plan.stages.map((stage:any)=><li key={stage.id}>{stage.id} · {stage.component}{stage.component==='SortRows'?` · 大小寫區分：${stage.case_sensitive?'是':'否'}`:''}</li>)}</ul>
        </>}
      </details>}
      {item.provider==='LOCAL_COPILOT' && <p>Copilot 回報：輸出 Token {item.usage?.output_tokens??'不可用'}；AI credits {item.usage?.ai_credits??'不可用'}；Premium requests {item.usage?.premium_requests??'不可用'}。</p>}
      <details><summary>審查版本指紋</summary><dl><dt>審查 ID</dt><dd>{item.invocation_id}</dd><dt>Context checksum</dt><dd>{item.context_checksum}</dd><dt>規格 checksum</dt><dd>{item.context.specification_checksum}</dd></dl></details>
      <p>此紀錄不是人工 QA 核准，也不能據此下載 Release ZIP。</p>
    </article>)}
    <QAApproval key={`${taskId}:${runId}`} taskId={taskId} runId={runId}/>
  </section>;
}
