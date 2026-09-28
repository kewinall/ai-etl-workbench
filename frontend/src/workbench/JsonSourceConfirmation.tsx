import {useState} from 'react';
import {request, jsonBody} from './api';
import {useTaskOperation} from './TaskDraftBoundary';

export function JsonSourceConfirmation({source, onChange, onBusy}: {
  source: any; onChange: (patch: any) => void; onBusy: (value: boolean) => void;
}) {
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const operation = useTaskOperation();
  const confirm = async () => {
    if (!operation.acquire()) return;
    setBusy(true); onBusy(true); setError('');
    try {
      const profile = await request(`/api/task-sources/${encodeURIComponent(source.upload_id)}/json-profile`, jsonBody('POST', {
        checksum: source.checksum, size: source.size,
      }));
      // Persist structure and its fingerprint, never raw preview data.
      onChange({fields: profile.fields, root_shape: profile.root_shape, row_count: profile.row_count,
        json_profile_binding_v1: profile.json_profile_binding_v1, profiled: true});
    } catch (e: any) {
      setError(e.message); onChange({json_profile_binding_v1: null});
    } finally {operation.release(); setBusy(false); onBusy(false)}
  };
  return <section className="panel form" aria-label="JSON 來源結構確認">
    <h4>確認 JSON 來源結構</h4>
    <p>支援單一物件或物件陣列，拒絕巢狀值與重複欄名；掃描全檔後綁定欄位及檔案指紋。型別仍是建議，不代表 Hop 執行或交付已核准。</p>
    <p>結構：{source.root_shape === 'ARRAY' ? '物件陣列' : source.root_shape === 'OBJECT' ? '單一物件' : '待確認'}；資料筆數：{source.row_count ?? '待確認'}。</p>
    <button type="button" disabled={busy} onClick={confirm}>{busy ? '正在確認…' : '確認 JSON 檔案與欄位'}</button>
    {error && <p role="alert">{error}</p>}
    <p role="status">{source.json_profile_binding_v1 ? '來源結構已確認；換檔後須重新確認。' : '尚未確認來源結構，不能建立 Task。'}</p>
  </section>;
}

export function JsonProfileSummary({source}: {source: any}) {
  if (source.type !== 'JSON') return null;
  return <section aria-label="已保存的 JSON 來源確認"><h4>JSON 來源確認</h4>
    {source.json_profile_binding_v1 ? <>
      <p>{source.root_shape === 'ARRAY' ? '物件陣列' : '單一物件'}；{source.json_profile_binding_v1.row_count} 筆。此確認不等於型別轉換驗證或執行核准。</p>
      <details><summary>來源結構指紋</summary><code>{source.json_profile_binding_v1.profile_checksum}</code></details>
    </> : <p>舊版或尚未確認的 JSON 來源；歷史仍可查看。新版受控執行須先以建立 Task 畫面上傳並確認來源，目前不提供舊版 JSON 原地換檔。</p>}
  </section>;
}
