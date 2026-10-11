import {useEffect, useState} from 'react';
import {request} from './api';

const explanations: Record<string, string> = {
  PROJECT_NOT_FOUND: '找不到 Task 所屬專案。',
  TASK_SETTINGS_INVALID: '本次 Task 的設定格式不合法，請修正執行設定後重新檢查。',
  SETTINGS_GROUP_INVALID: '平台設定格式不合法，請到平台設定中心修正對應分類後重新檢查。',
  AI_PROFILE_NOT_FOUND: '所選 AI Profile 不存在，請檢查專案預設值。',
  AI_PROFILE_DISABLED: '所選 AI Profile 已停用。',
  MODEL_ROUTE_MISSING: '此角色尚未指定模型；不會改用其他角色模型。',
  BEDROCK_MODEL_OR_REGION_MISSING: 'Bedrock 模型或 AWS region 尚未設定完整。',
  BEDROCK_ENDPOINT_UNSUPPORTED_USE_PROXY_PROFILE: '直接 Bedrock Profile 不接受自訂 endpoint，請改用 LiteLLM Proxy Profile。',
  AI_SECRET_UNAVAILABLE: '尚未設定此 AI Profile 的機密。',
  AI_PROVIDER_UNSUPPORTED: '此 Provider 尚未支援。',
  PROXY_ENDPOINT_INVALID: 'LiteLLM Proxy endpoint 格式不合法。',
  CONNECTION_NOT_CONFIGURED: 'Vertica 連線只有名稱或尚未建立，缺少可用連線設定。',
  ETL_CONNECTION_NOT_ALLOWED: '平台控制資料庫不可作為 ETL 目標。',
  CONNECTION_FIELD_MISSING: 'Vertica 連線必要欄位尚未填寫。',
  CONNECTION_PORT_INVALID: '連線 Port 必須是 1–65535 的整數。',
};
const roles: Record<string, string> = {requirement_gate: 'SA', etl_specification: 'Developer', qa_review: 'QA'};
const groups: Record<string, string> = {ai_provider_model_strategy: 'AI 供應商與模型', data_connections_targets: '資料連線與目標'};

export function ExecutionReadiness({taskId}: {taskId: string}) {
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    setResult(null); setError('');
    request(`/api/tasks/${encodeURIComponent(taskId)}/execution-settings`)
      .then(value => {
        if (!['BLOCKED', 'CONFIGURED_NOT_TESTED'].includes(value?.status) || !Array.isArray(value.issues) ||
            (value.status === 'CONFIGURED_NOT_TESTED' && value.issues.length > 0)) {
          throw new Error('設定檢查回應不完整，無法確認準備狀態；請重新檢查。');
        }
        if (active) setResult(value);
      })
      .catch(err => {if (active) setError(err.message)});
    return () => {active = false};
  }, [taskId, refresh]);
  return <section className="panel" style={{padding: 20, marginBottom: 20}} aria-label="Pilot 執行準備">
    <h3>Pilot 執行準備</h3>
    <p>檢查專案設定與角色路由，不會呼叫 AI、測試連線或執行 ETL。</p>
    {error && <p role="alert">無法檢查：{error}</p>}
    {!result && !error && <p role="status">正在檢查設定…</p>}
    {result && <>
      <p><strong>{result.status === 'BLOCKED' ? '設定尚未完整' : '設定完整，尚未測試連線'}</strong> · {result.execution_enabled ? '執行開關已開啟' : 'ETL 執行開關已關閉'}</p>
      <p>設定快照與初步檢查不代表完整 ETL 已接通；這不是可執行或交付核准。</p>
      {!!result.issues?.length && <ul>{result.issues.map((issue: any, index: number) =>
        <li key={index}>{issue.role && `${roles[issue.role] || issue.role}：`}{explanations[issue.code] || issue.code}{issue.group && `（${groups[issue.group] || '未識別分類'}）`}{issue.field && `（${issue.field}）`}</li>)}</ul>}
    </>}
    <div style={{display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 12}}>
      <a href="#/system">前往平台設定中心</a>
      <button type="button" disabled={!result && !error} onClick={() => setRefresh(value => value + 1)}>重新檢查設定</button>
    </div>
  </section>;
}
