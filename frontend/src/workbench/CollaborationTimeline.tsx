import {useEffect, useState} from 'react';
import {request} from './api';

// Readable, read-only timeline for one Run: human decisions, control events and SA/Developer/QA model records.
// Restored from the pre-seven-stage Task view; it never calls models or replays ETL.
const time = (value: string) => value ? new Date(value).toLocaleString() : '未記錄';
const eventLabels: Record<string, string> = {ENQUEUED: '保存準備版本', INPUT_APPROVE: '人工確認輸入', INPUT_REJECT: '人工拒絕輸入', CLAIMED: '控制程式領取', REQUIREMENT_GATE_STARTED: '開始需求檢查', PIPELINE_NOT_READY: '初步檢查完成，後續流程尚未接通', REQUIREMENT_NEEDS_INPUT: '需求缺漏，等待補正', SA_QUEUED: '人工授權 SA 並排隊', SA_DISPATCH_RESERVED: '保存 SA 派發意圖', SA_VALIDATED_NOT_APPROVED: 'SA 結構驗證通過，等待人工核准', OPERATOR_CANCELLED: '人工取消版本'};

export function CollaborationTimeline({taskId, runId}: {taskId: string; runId: string}) {
  const selected = runId;
  const [detail, setDetail] = useState<any>(null);
  const [invocation, setInvocation] = useState<any>(null);
  const [roles, setRoles] = useState<any[]>([]);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let live = true;
    setDetail(null); setInvocation(null); setError(''); setRoles([]);
    if (selected) Promise.all([request(`/api/tasks/${taskId}/runs/${selected}`), request(`/api/tasks/${taskId}/runs/${selected}/sa-invocation`)])
      .then(([run, sa]) => {if (live) {setDetail(run); setInvocation(sa.invocation)}}).catch(e => live && setError(e.message));
    if (selected) Promise.all(['developer','qa-review'].map(async endpoint => {
      const role = endpoint === 'developer' ? 'Developer' : 'QA';
      try {
        const data = await request(`/api/tasks/${taskId}/runs/${selected}/${endpoint}`);
        return {role, records: data.history ?? (data.invocation ? [data.invocation] : [])};
      } catch (e: any) {return {role, error: e.message, records: []}}
    })).then(value => {if (live) setRoles(value)});
    return () => {live = false};
  }, [taskId, selected, refresh]);
  return <section className="panel" aria-label="版本協作紀錄">
    <h3>版本協作紀錄</h3><p>分別呈現人工決定、控制程式事件與 SA／Developer／QA 模型紀錄。檢視不會呼叫模型或重跑 ETL；AI 建議不等於人工核准。</p>
    <button type="button" onClick={() => setRefresh(n => n + 1)}>重新讀取此版本紀錄</button>
    {error && <p role="alert">無法讀取紀錄：{error}</p>}
    {!detail && !error && <p role="status">正在讀取此版本紀錄…</p>}
    {detail && <>
      <p>Run：{detail.run_id} · 輸入 checksum：{detail.input_checksum}</p>
      <p>{detail.matches_current ? '符合目前輸入與設定。' : '歷史版本，不能沿用為目前核准。'}</p>
      {detail.approval && <article className="wb-record"><b>人工操作 · 輸入確認</b><p>{detail.approval.decision}；不等於 Hop 執行或 Release 核准。</p></article>}
      <h4>控制程式事件（依保存順序）</h4>
      {detail.events?.length ? <ol className="wb-timeline">{detail.events.map((event: any) => <li key={event.event_id}>
        <b>{event.event_type === 'SDM_CANDIDATE_SAVED' ? '程式工具保存 SDM 候選文件（非 Release）' : event.event_type === 'SPECIFICATION_SAVED' ? '程式驗證後保存規格' : event.event_type === 'SPECIFICATION_APPROVED' ? '人工核准規格（非執行授權）' : eventLabels[event.event_type] || '控制流程事件'}</b>
        <small>{time(event.created_at)} · {event.event_type} · {event.phase}</small>
        {event.event_type === 'SDM_CANDIDATE_SAVED' ? <p>候選文件：{event.event_context.sdm_id}<br/>規格 checksum：{event.event_context.specification_checksum}<br/>文件 checksum：{event.event_context.checksum}</p> : event.event_context?.specification_id && <p>規格第 {event.event_context.version} 版 · {event.event_context.specification_id}<br/>內容 checksum：{event.event_context.checksum}</p>}
        {event.event_context?.approval_id && <p>核准紀錄：{event.event_context.approval_id}。這是當時的操作紀錄；目前是否有效，請以對應階段的目前狀態為準。</p>}
        {event.event_type === 'SPECIFICATION_SEMANTIC_REJECTED' && <section aria-label="規格語意攔截證據">
          <p>程式驗證拒絕保存規格，未授權執行。此紀錄保留被攔截的差異，不代表修正版本已通過。</p>
          <ul>{event.event_context.issues.map((issue: any, index: number) => <li key={index}>{issue.message} · {issue.field_path}
            {issue.node_id && <span> · 節點 {issue.node_id}</span>}
            {'expected' in issue && <span> · 預期 {JSON.stringify(issue.expected)}；實際 {JSON.stringify(issue.actual)}</span>}
          </li>)}</ul><p>提案指紋：{event.event_context.proposed_checksum}</p>
        </section>}
      </li>)}</ol> : <p>此版本尚無控制事件。</p>}
      <h4>AI 角色：SA</h4>
      {invocation ? <article className="wb-record"><p>{invocation.model} · {invocation.status}</p><p>此紀錄不等於需求已核准。模型輸出、引用及用量請至「需求審查」階段查閱同一版本。</p></article> : <p>此版本尚無 SA 呼叫紀錄。</p>}
      {!roles.length && <p role="status">正在讀取 Developer／QA 紀錄…</p>}
      {roles.map(role => <section key={role.role} aria-label={`${role.role} 模型紀錄`}>
        <h4>AI 角色：{role.role}</h4>
        {role.error ? <p role="alert">無法讀取 {role.role}：{role.error}；不能判定沒有紀錄。</p>
          : !role.records.length ? <p>此版本尚無 {role.role} 呼叫紀錄；不代表已通過。</p>
          : role.records.map((item: any) => <article className="wb-record" key={item.invocation_id}>
            <p>{item.model} · {item.status} · {time(item.created_at)}</p>
            {item.review && <p>QA 建議：{item.review.status} · {item.review.summary}</p>}
            <p>模型耗時：{item.duration_ms == null ? '未提供' : `${item.duration_ms} ms`}；Token：{item.usage?.total_tokens ?? '未提供'}</p>
            <p>此為保存的模型紀錄，不代表目前核准有效。完整輸出與核准請至「{role.role === 'QA' ? '品質審查' : '流程設計審查'}」階段查看相同版本。</p>
          </article>)}
      </section>)}
    </>}
  </section>;
}
