export const ordinalRef = '$source_order.source.0';

export function validateOrderDraft(order: any, intent: any) {
  if (!order) return;
  if (!/^[a-z_][a-z0-9_]{0,62}$/.test(order.ordinal_column || '')) throw new Error('來源序號名稱須為小寫英文、數字或底線，且不能以數字開頭。');
  if (!intent || intent.invalid || intent.filters.length || intent.aggregation || !intent.output_columns.includes(ordinalRef)) {
    throw new Error('保留來源順序須不篩選、不聚合，並在輸出欄位保留來源序號；請先補正轉換意圖。');
  }
}

export function SourceOrderSummary({value}: {value: any}) {
  if (!value) return null;
  return <section aria-label="來源順序設定"><h4>來源順序</h4>{value.invalid ? <p>設定不完整，請補正。</p> : <>
    <p>保留 CSV 原始資料列順序，序號欄位：<code>{value.ordinal_column}</code>（BIGINT）。</p>
    <p>序號從 1 開始，按邏輯資料列產生；不是依 record_id 大小排序。讀取結果時須依序號升冪排序。</p>
  </>}</section>;
}

export function SourceOrderEditor({value, eligible, disabled, onChange}: {value: any; eligible: boolean; disabled: boolean; onChange: (value: any) => void}) {
  return <fieldset disabled={disabled}><legend>保留來源順序</legend>
    <p>僅支援單一 CSV 全列投影。啟用後新增系統產生的序號輸出，不刪除原有篩選或聚合；若有衝突須先補正。保存後需重新確認命名與規格。</p>
    {!value ? <button type="button" disabled={!eligible} onClick={() => onChange({version: 1, source_ref: 'source.0', ordinal_column: 'source_position', direction: 'ASC', semantics: 'LOGICAL_CSV_RECORD_POSITION'})}>啟用保留來源順序</button> : <>
      <label>來源序號英文欄位<input required maxLength={63} pattern="[a-z_][a-z0-9_]{0,62}" value={value.ordinal_column || ''} onChange={e => onChange({...value, ordinal_column: e.target.value})}/></label>
      <p>系統欄位代號：{ordinalRef}。型別固定 BIGINT；需在輸出欄位及命名契約保留此欄位。</p>
    </>}
    {!eligible && <p>目前來源不是可確認的單一 CSV，不能啟用此功能。</p>}
  </fieldset>;
}
