import {useEffect, useState} from 'react';
import {jsonBody, request} from './api';

export function DeveloperInvocation({taskId, runId}: {taskId: string; runId: string}) {
  const base = `/api/tasks/${encodeURIComponent(taskId)}/runs/${runId}/developer`;
  const [data, setData] = useState<any>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let live = true;
    request(base).then(value => {if (live) setData(value)}).catch(err => {if (live) setError(err.message)});
    return () => {live = false};
  }, [base]);
  async function load() {
    setBusy(true); setError(''); setData(null); setConfirmed(false);
    try {setData(await request(base))} catch (err: any) {setError(err.message)} finally {setBusy(false)}
  }
  async function authorize() {
    setBusy(true); setError('');
    try {
      await request(`${base}/authorize`, jsonBody('POST', {confirmed,
        context_checksum: data.context.context_checksum, prompt_checksum: data.prompt_checksum,
        schema_checksum: data.schema_checksum, model: data.model}));
      setData(await request(base)); setConfirmed(false);
    } catch (err: any) {setData(null); setConfirmed(false); setError(err.message)}
    finally {setBusy(false)}
  }
  const item = data?.invocation;
  return <section aria-label="Developer 設計協作">
    <h4>Developer 設計協作</h4>
    <p>根據已人工確認的 SA 建議與命名契約提出規格。程式驗證及保存後，仍需另行核准規格；不會自動執行 ETL。</p>
    <button disabled={busy} onClick={load}>重新載入 Developer 狀態</button>
    {error && <p role="alert">{error}。未重新送出模型請求，請重新核對。</p>}
    {data && !item && <>
      {!data.eligible ? <p>尚不符合派發條件：請先確認 SA 建議與命名契約，並使用已設定的本機 Copilot 路由。</p>
        : !data.dispatch_enabled ? <p>部署尚未啟用 Developer 派發，不會呼叫模型。</p> : <>
          <p>模型：{data.model}。一次 Copilot CLI，不自動重試、換模型或使用工具；無輸出 Token 硬上限，使用已登入帳號額度。本機 Developer Worker 必須另行執行，授權不代表已上線。</p>
          <label><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)}/>我同意此版本的 Developer 單次模型呼叫與用量</label>
          <button disabled={busy || !confirmed} onClick={authorize}>授權 Developer 設計</button>
        </>}
    </>}
    {item && <>
      <p>模型：{item.model}；狀態：{item.status === 'DEVELOPER_RESERVED' ? '已授權，等待本機 Worker 領取或回報（請勿重送）'
        : item.status === 'VALIDATED_NOT_APPROVED' ? '設計已保存，待人工核准規格'
        : item.status === 'STALE_RESULT_NEEDS_REVIEW' ? '上游版本已變更，結果僅保留歷史'
        : '呼叫結果不明，須人工核對，不會自動重試'}</p>
      {!data.matches_current && <p>此結果不符合目前可派發版本，不能據此授權新的執行。</p>}
      {item.proposal && <><p>{item.proposal.summary}</p><p>引用證據：{item.proposal.evidence_ids?.join('、')}</p></>}
      {item.specification && <p>規格版本 {item.specification.version} 已保存。請在下方「規格」區重新載入並檢視後核准。</p>}
      <p>輸出 Token：{item.usage?.output_tokens ?? '不可用'}；AI credits：{item.usage?.ai_credits ?? '不可用'}；Premium requests：{item.usage?.premium_requests ?? '不可用'}。缺值不當作零，不估算費用。</p>
    </>}
  </section>;
}
