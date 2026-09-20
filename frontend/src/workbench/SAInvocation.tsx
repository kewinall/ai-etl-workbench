import {useEffect, useState} from 'react';
import {request, jsonBody} from './api';
import {WorkerStatus} from './WorkerStatus';
import {SAApproval} from './SAApproval';

const states: Record<string, string> = {
  SA_QUEUED: '已授權並排隊，尚未由 Worker 領取',
  CANCELLED_NOT_DISPATCHED: '已取消排隊，未呼叫模型；重新嘗試需建立新版本',
  STALE_NOT_DISPATCHED: '設定或版本已變更，未派發模型；請建立新版本重新確認',
  DISPATCH_RESERVED: '已保存派發意圖；呼叫結果尚未確認，請勿重送',
  VALIDATED_NOT_APPROVED: '結構驗證通過，尚未人工核准',
  STALE_RESULT_NEEDS_REVIEW: '上游版本已變更，此結果僅供歷史查閱',
  OUTCOME_UNKNOWN_NEEDS_REVIEW: '結果未明，需人工核對；不會自動重送',
};

export function SAInvocation({taskId, runId}: {taskId: string; runId: string}) {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [offer, setOffer] = useState<any>(null);
  const [consent, setConsent] = useState(false);
  const load = async () => {
    setBusy(true); setError('');
    try {
      const [record, authorization] = await Promise.all([
        request(`/api/tasks/${taskId}/runs/${runId}/sa-invocation`),
        request(`/api/tasks/${taskId}/runs/${runId}/sa-authorization`),
      ]);
      setData(record); setOffer(authorization);
    }
    catch (error: any) {setError(error.message)} finally {setBusy(false)}
  };
  useEffect(() => {load()}, [taskId, runId]);
  useEffect(() => {setConsent(false)}, [taskId, runId, offer?.authorization?.context_checksum, offer?.authorization?.settings_checksum]);
  useEffect(() => {
    if (!['SA_QUEUED', 'DISPATCH_RESERVED'].includes(data?.invocation?.status)) return;
    const timer = window.setInterval(load, 5000);
    return () => window.clearInterval(timer);
  }, [taskId, runId, data?.invocation?.status]);
  const authorize = async () => {
    if (!consent || !offer?.dispatch_enabled || !offer?.eligible) return;
    setBusy(true); setError('');
    try {
      await request(`/api/tasks/${taskId}/runs/${runId}/sa-authorization`, jsonBody('POST', offer.authorization));
      setConsent(false); await load();
    } catch (error: any) {
      setError(`授權結果需核對：${error.message}。請先重新載入狀態；相同版本不會建立第二次呼叫。`);
    } finally {setBusy(false)}
  };
  const item = data?.invocation;
  const cancelQueued = async () => {
    setBusy(true); setError('');
    try {await request(`/api/tasks/${taskId}/runs/${runId}/sa-invocation/cancel`, {method: 'POST'}); await load()}
    catch (error: any) {setError(`無法取消：${error.message}。請重新載入並核對是否已被領取。`)}
    finally {setBusy(false)}
  };
  return <section aria-label="SA 呼叫狀態">
    <h4>SA 呼叫狀態</h4>
    <p>查閱不會呼叫模型。只有明確授權後才會排隊；SA 建議不等於 ETL 執行或 Release 核准。</p>
    {offer && <WorkerStatus kind={offer.authorization.policy_version === 'copilot-cli-once-v1' ? 'SA_COPILOT' : 'SA_LITELLM'}/>}
    <button disabled={busy} onClick={load}>重新載入 SA 狀態</button>
    {error && <p role="alert">{error}</p>}
    {offer && !item && <div>
      {!offer.dispatch_enabled ? <p>部署尚未啟用 SA 派發；目前不會呼叫模型。</p> : !offer.eligible ? <p>請先確認目前輸入並通過需求檢查，才可授權 SA。</p> : <>
        <p>模型：{offer.model}。{offer.authorization.policy_version === 'copilot-cli-once-v1'
          ? '使用本機 Copilot 登入及額度；只啟動 1 次 CLI，不自動重試、不允許工具操作。CLI 無法保證輸出 Token 硬上限，實際用量以回報為準；Windows 本機 Worker 必須執行中。'
          : '可能依 Token 計費；包含暫時性錯誤重試與格式補正，最多 4 次供應商請求，每次最多 2,048 個輸出 Token。'}費率及最終費用尚不可用；授權不代表 Worker 已上線。</p>
        <label><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)}/>我同意此版本的 SA 模型呼叫及上述用量限制</label>
        <button disabled={busy || !consent} onClick={authorize}>授權並排入 SA 工作</button>
      </>}
    </div>}
    {data && !item && <p>此版本尚無 SA 派發紀錄。</p>}
    {item && <>
      {item.review && <p><strong>SA 審查結果：{item.review.status === 'NEEDS_INPUT' ? '需要補正需求' : '待人工審查'}</strong>（不代表執行核准）</p>}
      <p>{states[item.status] || '未知狀態，請人工核對'}</p>
      {item.status === 'SA_QUEUED' && <button disabled={busy} onClick={cancelQueued}>取消尚未領取的 SA 工作</button>}
      {!data.matches_current && <p>此版本已不符合目前 Task／設定，不可沿用核准。</p>}
      <dl><dt>呼叫編號</dt><dd>{item.invocation_id}</dd><dt>Provider／模型</dt><dd>{item.provider}／{item.model}</dd><dt>Prompt 版本</dt><dd>{item.prompt_version ?? '未記錄'}</dd><dt>Context checksum</dt><dd>{item.context_checksum}</dd><dt>模型處理時間</dt><dd>{item.duration_ms == null ? '不可用' : `${item.duration_ms} ms`}</dd><dt>Token</dt><dd>{item.usage?.usage_type === 'EXACT' && item.usage.total_tokens != null ? item.usage.total_tokens : '不可用（不當作零）'}</dd></dl>
      {item.error_code && <p>處理代碼：{item.error_code}。請先核對設定與呼叫紀錄，不要直接重送。</p>}
      {item.provider === 'LOCAL_COPILOT' && <p>Copilot 回報：AI credits {item.usage?.ai_credits ?? '不可用'}；Premium requests {item.usage?.premium_requests ?? '不可用'}；輸出 Token {item.usage?.output_tokens ?? '不可用'}。僅顯示 CLI 實際回報，未推算費用。</p>}
      {item.review && <><h5>SA 建議（非執行核准）</h5><p>{item.review.summary}</p><p>建議狀態：{item.review.status === 'NEEDS_INPUT' ? '需要補正' : '待人工審查'}</p><p>引用：{item.review.evidence_ids.join('、')}</p><ul>{item.review.issues.map((issue: any, index: number) => <li key={index}>{issue.message}（{issue.evidence_ids.join('、')}）</li>)}</ul></>}
    </>}
    <SAApproval key={`${runId}-${data?.invocation?.status}-${data?.matches_current}`} base={`/api/tasks/${encodeURIComponent(taskId)}/runs/${runId}`}/>
  </section>;
}
