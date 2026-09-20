const failures: Record<string, string> = {
  UPLOAD_BINDING_INVALID: '檔案版本資訊不完整，請重新上傳並建立待確認版本。',
  UPLOAD_CONTENT_CHANGED: '檔案內容或大小與核准版本不同，不能沿用原確認。',
  UPLOAD_UNAVAILABLE: '找不到檔案或無法讀取，可能已超過保存期限。',
  UPLOAD_PATH_INVALID: '來源不是允許的受控檔案，請使用平台上傳。',
  CSV_CONTENT_INVALID: 'CSV 內容不符合本版本的解析契約，請查看下方原因。',
};
const csvIssues: Record<string, string> = {
  CSV_BYTES_REQUIRED:'未取得檔案內容', CSV_SIZE_LIMIT:'超過可驗證大小上限',
  CSV_CONTRACT_INVALID:'編碼、分隔符號或欄位政策尚未完整確認',
  CSV_SOURCE_COLUMNS_INVALID:'來源欄位定義無效或重複',
  CSV_BOM_CONTRACT_MISMATCH:'檔案含 BOM，與選擇的 UTF-8 契約不同',
  CSV_ENCODING_INVALID:'檔案無法以指定編碼解析', CSV_NUL_CHARACTER:'檔案含不支援的空字元',
  CSV_HEADER_MISSING:'缺少標題列', CSV_HEADER_DUPLICATE:'標題欄位名稱重複',
  CSV_HEADER_MISMATCH:'標題名稱或順序與確認欄位不同', CSV_EXTRA_COLUMNS:'存在政策不允許的額外欄位',
  CSV_MISSING_COLUMNS:'資料缺少必要欄位', CSV_RECORD_LIMIT:'超過可驗證筆數上限',
  CSV_PARSE_ERROR:'CSV 引號或記錄結構無法解析', CSV_DATA_EMPTY:'沒有資料記錄',
};

export function SourceEvidence({items}: {items?: any[]}) {
  return <section aria-label="來源檔案驗證證據" className="source-evidence">
    <h4>來源檔案驗證</h4>
    <p>這是此版本當時的檢查紀錄，不代表檔案現在仍相同，也不是資料匯入筆數、ETL 成功或交付核准。</p>
    {!items?.length ? <p>此版本沒有實體來源檔案檢查證據；不能視為通過。可能是合成来源或較早的紀錄。</p> : items.map((item, index) => <article key={index}>
      <h5>來源 {index + 1} · {item.source_ref}</h5>
      <p>{item.status === 'UPLOAD_BYTES_VERIFIED' ? '檔案完整性：符合此版本的大小與 checksum。' : failures[item.status] || '來源驗證狀態無法辨識，請查閱控制紀錄；不可視為通過。'}</p>
      {Number.isSafeInteger(item.byte_count) && <p>已核對檔案大小：{item.byte_count.toLocaleString()} bytes</p>}
      {item.csv && <>
        <p>CSV 結構：{item.csv.status === 'CSV_STRUCTURE_VALIDATED_NOT_EXECUTABLE' && item.csv.complete === true ? '檢查通過（不含型別或業務邏輯驗證）' : '未通過或尚未完整掃描'}</p>
        <p>已檢查資料記錄：{Number.isSafeInteger(item.csv.records_checked) ? item.csv.records_checked.toLocaleString() : '未提供'}；掃描{item.csv.complete === true ? '完整' : '未完成'}。</p>
        {!!item.csv.issues?.length && <ul>{item.csv.issues.map((issue:any, n:number) => <li key={n}>{csvIssues[issue.code] || '未分類的 CSV 檢查問題'}{issue.record === 0 ? '（標題列）' : Number.isSafeInteger(issue.record) ? `（資料記錄 ${issue.record}，非文字行號）` : ''}</li>)}</ul>}
      </>}
      {typeof item.content_checksum === 'string' && /^[0-9a-f]{64}$/.test(item.content_checksum) && <details><summary>查看內容指紋（SHA-256）</summary><code style={{overflowWrap:'anywhere',whiteSpace:'normal'}}>{item.content_checksum}</code></details>}
      {item.status !== 'UPLOAD_BYTES_VERIFIED' && <p>請先核對檔案與解析設定。符合修訂條件的單一 CSV，可由「補正需求並建立新版」更換檔案；其他來源尚未支援換檔修訂。</p>}
    </article>)}
  </section>;
}
