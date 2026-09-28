import {useState} from 'react';
import {request, jsonBody} from './api';
import {useTaskOperation} from './TaskDraftBoundary';

export function ExcelSourceSelection({source, onChange, onBusy}: {
  source: any; onChange: (patch: any) => void; onBusy: (value: boolean) => void;
}) {
  const [worksheet, setWorksheet] = useState(source.worksheet || (source.worksheets?.length === 1 ? source.worksheets[0] : ''));
  const [header, setHeader] = useState(String(source.header_row || 1));
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const operation = useTaskOperation();
  const invalidate = () => {setError(''); onChange({excel_selection_v1: null, fields: [], selection_required: true})};
  const valid = !!worksheet && /^\d+$/.test(header) && Number(header) >= 1 && Number(header) <= 1000;
  const select = async () => {
    if (!valid || !operation.acquire()) return;
    setBusy(true); onBusy(true); setError('');
    try {
      const result = await request(`/api/task-sources/${encodeURIComponent(source.upload_id)}/excel-profile`, jsonBody('POST', {
        checksum: source.checksum, size: source.size, worksheet, header_row: Number(header),
      }));
      // Persist selection metadata, not the raw preview rows returned by profiling.
      onChange({worksheet: result.worksheet, worksheets: result.worksheets, header_row: result.header_row,
        fields: result.fields, excel_selection_v1: result.excel_selection_v1,
        selection_required: false, profiled: true});
    } catch (e: any) {
      setError(e.message); onChange({excel_selection_v1: null, fields: [], selection_required: true});
    } finally {operation.release(); setBusy(false); onBusy(false)}
  };
  return <section aria-label="Excel 工作表與標頭確認" className="panel form wb-excel-selection">
    <h4>確認 Excel 來源結構</h4>
    <p>請選擇工作表與欄名所在列。解析最多 20 筆樣本，僅提供型別建議，不代表全檔驗證或 Hop 執行核准。</p>
    <label>Excel 工作表<select value={worksheet} disabled={busy} onChange={e => {setWorksheet(e.target.value); invalidate()}}>
      <option value="">請選擇工作表</option>{(source.worksheets || []).map((name: string) => <option key={name} value={name}>{name}</option>)}
    </select></label>
    <label>Excel 標頭列<input type="number" min="1" max="1000" value={header} disabled={busy} onChange={e => {setHeader(e.target.value); invalidate()}}/></label>
    <button type="button" disabled={busy || !valid} onClick={select}>{busy ? '正在解析…' : '解析並確認此工作表'}</button>
    {error && <p role="alert">{error}</p>}
    {source.excel_selection_v1 ? <p role="status">已確認：{source.worksheet}，第 {source.header_row} 列標頭，{source.fields.length} 個欄位；修改選擇後須重新確認。</p>
      : <p role="status">尚未確認來源結構，不能建立 Task。</p>}
  </section>;
}

export function ExcelSelectionSummary({source}: {source: any}) {
  if (source.type !== 'EXCEL') return null;
  return <section aria-label="已保存的 Excel 來源選擇" className="wb-excel-selection">
    <h4>Excel 來源選擇</h4>
    {source.excel_selection_v1 ? <>
      <p>已確認：{source.worksheet}，第 {source.header_row} 列標頭。</p>
      <p>僅確認來源選擇與樣本欄位，不代表全檔驗證或執行核准。</p>
      <details><summary>來源選擇指紋</summary><code>{source.excel_selection_v1.profile_checksum}</code></details>
    </> : <p>舊版或尚未確認的來源設定；沒有新版工作表與標頭確認證據。</p>}
  </section>;
}
