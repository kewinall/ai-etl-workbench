export function excelDraft(selection: any, evidence: any) {
  return evidence?.contract_status === 'CONFIRMED_INPUT_ONLY' ? {...evidence.contract} : {
    version: 1, engine: 'POI', worksheet: selection.worksheet, header_row: selection.header_row,
    blank_rows: '', missing_cells: 'NULL', extra_columns: 'REJECT', formulas: 'REJECT',
    trim_strings: 'NONE', on_error: 'FAIL',
  };
}

export function ExcelInputSummary({value}: {value: any}) {
  if (!value) return null;
  return <section aria-label="Excel 讀取契約摘要"><h4>Excel 讀取契約</h4>
    {value.contract_status === 'CONFIRMED_INPUT_ONLY' ? <>
      <p>工作表：{value.contract.worksheet}；標頭：第 {value.contract.header_row} 列；空白列：{value.contract.blank_rows === 'SKIP' ? '跳過' : '保留為 NULL'}。</p>
      <p>缺值保留 NULL、字串不修剪；公式、額外欄位及無法符合型別的資料會被拒絕。</p>
    </> : <p>尚未確認讀取政策，請補正並建立新版。來源選擇不等於讀取契約或執行核准。</p>}
  </section>;
}

export function ExcelInputEditor({selection, value, disabled, onChange, evidence}: {
  selection: any; value: any; disabled: boolean; onChange: (value: any) => void; evidence: any;
}) {
  if (!selection) return null;
  return <fieldset disabled={disabled}><legend>Excel 讀取契約補正</legend>
    <p>工作表「{selection.worksheet}」、第 {selection.header_row} 列標頭已綁定來源。此處不換檔、不修改原始資料。</p>
    {!value ? <button type="button" onClick={() => onChange(excelDraft(selection, evidence))}>設定 Excel 讀取契約</button> : <>
      <label>Excel 空白列處理<select required value={value.blank_rows} onChange={event => onChange({...value, blank_rows: event.target.value})}>
        <option value="">請明確選擇</option><option value="SKIP">跳過全空白列</option><option value="PRESERVE">保留全空白列（各欄為 NULL）</option>
      </select></label>
      <p>固定保護：缺值為 NULL、字串不修剪、拒絕公式與額外欄位；型別不符即停止，不截斷或自動修正資料。</p>
      <p>以原生 Excel 引擎讀取；保存後須重新確認新版輸入，不沿用舊版核准。</p>
      <button type="button" onClick={() => onChange(null)}>不變更 Excel 契約</button>
    </>}
  </fieldset>;
}
