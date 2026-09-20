import {useState} from 'react';
import {request} from './api';

const kinds: Record<string, string> = {REQUIREMENT: '需求文字', TARGET: '目標', CONDITIONS: '使用者確認條件', SOURCE_FIELD: '來源欄位', CSV_INPUT: 'CSV 輸入契約'};
const labels: Record<string, string> = {schema: 'Schema', table: 'Table', version: '版本', write_mode: '寫入模式', date_scope: '資料期間', date_column: '日期欄位', start_date: '起日（包含）', end_date_exclusive: '迄日（不包含）', key_columns: '鍵欄位', name: '名稱', type: '型別', invalid: '條件格式不合法'};

export function SAEvidence({taskId, runId}: {taskId: string; runId: string}) {
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const load = async () => {
    setBusy(true); setError('');
    try {setResult(await request(`/api/tasks/${taskId}/runs/${runId}/sa-context`))}
    catch (error: any) {setError(error.message)} finally {setBusy(false)}
  };
  return <section aria-label="SA 需求證據">
    <h4>SA 需求證據</h4>
    <p>只查看此版本的需求與來源欄位，不呼叫模型。引用存在不代表語意正確，仍須驗證及人工確認。</p>
    <button disabled={busy} onClick={load}>查看 SA 證據清單</button>
    {error && <p role="alert">{error}</p>}
    {result && <>
      <p>此證據檢視不會呼叫模型；{result.matches_current ? '此版本與目前設定一致。' : '這是歷史版本，不能沿用為目前核准。'}</p>
      <p>程式檢查：{result.context.deterministic_gate.status === 'CHECKED' ? '初步通過，非執行核准' : '仍有需求缺口，SA 不可推翻此阻擋'}</p>
      <p>Context checksum：{result.context.context_checksum}</p>
      <p>{result.context_origin === 'CAPTURED_AT_AUTHORIZATION' ? '顯示授權當時保存的 Context，不以新版規則改寫歷史。' : '這是目前規則產生的預覽，尚未派發模型。'}</p>
      <ol>{result.context.evidence.map((item: any) => <li key={item.id}>
        <strong>{kinds[item.kind] || item.kind} · {item.id}</strong>
        {typeof item.value === 'string' ? <p>{item.value || '未提供'}</p> : <dl>{Object.entries(item.value).map(([key, value]) => <div key={key}><dt>{labels[key] || key}</dt><dd>{Array.isArray(value) ? value.join('、') || '未提供' : value === null || value === '' ? '未提供' : String(value)}</dd></div>)}</dl>}
      </li>)}</ol>
    </>}
  </section>;
}
