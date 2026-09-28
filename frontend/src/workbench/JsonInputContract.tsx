export function jsonDraft(profile: any) {
  return {version: 1, encoding: 'UTF-8-SIG', bom_handling: 'REMOVE_UTF8_BOM', root_shape: profile.root_shape,
    missing_keys: 'NULL', extra_keys: 'REJECT', nested_values: 'REJECT', duplicate_keys: 'REJECT',
    trim_strings: 'NONE', null_records: 'PRESERVE', on_error: 'FAIL'};
}

function PolicyDescription() {
  return <dl>
    <dt>編碼與 BOM</dt><dd>UTF-8；讀取副本僅移除開頭 BOM，保留原檔與雙方指紋。</dd>
    <dt>缺值與空字串</dt><dd>缺少欄位及明確 null 保留為 NULL；空字串與前後空白不修改。</dd>
    <dt>結構保護</dt><dd>拒絕額外欄位、巢狀值及重複欄名；全 NULL 紀錄不略過。</dd>
    <dt>錯誤處理</dt><dd>讀取錯誤即停止，不忽略錯誤或自動修正資料。</dd>
  </dl>;
}

export function JsonInputSummary({value}: {value: any}) {
  if (!value) return null;
  return <section aria-label="JSON 讀取契約摘要"><h4>JSON 讀取契約</h4>
    {value.contract_status === 'CONFIRMED_INPUT_ONLY' ? <>
      <p>已確認：{value.contract.root_shape === 'ARRAY' ? '物件陣列' : '單一物件'}。</p><PolicyDescription/>
      <p>只確認讀取政策，不等於型別轉換驗證、Hop 執行或交付核准。</p>
    </> : <p>尚未確認讀取政策，請補正並建立新版；沒有來源確認證據的舊版 JSON 須重新建立已確認來源的 Task。</p>}
  </section>;
}

export function JsonInputEditor({profile, value, disabled, onChange}: {
  profile: any; value: any; disabled: boolean; onChange: (value: any) => void;
}) {
  if (!profile) return null;
  return <fieldset disabled={disabled}><legend>JSON 讀取契約補正</legend>
    <p>已確認來源：{profile.root_shape === 'ARRAY' ? '物件陣列' : '單一物件'}，{profile.row_count} 筆；此處不換檔、不修改原始資料。</p>
    <PolicyDescription/>
    <label><input type="checkbox" checked={!!value} onChange={e => onChange(e.target.checked ? jsonDraft(profile) : null)}/>
      我確認以上 JSON 讀取政策，保存至新版本</label>
    <p>保存後仍須重新確認新版輸入，不沿用舊核准。</p>
  </fieldset>;
}
