import {JsonInputSummary} from './JsonInputContract';
import {ExcelInputSummary} from './ExcelInputContract';

export function QASourceEvidence({details}: {details: any}) {
  const csv = (contract: any, validation: any, label: string) => <section key={label} aria-label={label}>
    <h5>{label}</h5><p>編碼：{contract.encoding}；標題列：{contract.header ? '有' : '無'}；額外欄位：{contract.extra_columns === 'REJECT' ? '拒絕' : contract.extra_columns}。</p>
    <p>來源完整掃描：{validation?.records_checked ?? '未提供'} 筆。</p>
  </section>;
  return <section aria-label="QA 來源證據"><h5>來源讀取證據</h5>
    <p>整批結構檢查在 Hop 前執行；本證據重新核對相同指紋的來源，不重跑 ETL，也不等於模型或交付核准。</p>
    {details.source_format === 'JSON' ? <>
      <JsonInputSummary value={{contract_status: details.json_input_contract ? 'CONFIRMED_INPUT_ONLY' : 'MISSING_OR_INVALID', contract: details.json_input_contract}}/>
      <p>來源完整掃描：{details.json_structure_validation?.records_expected ?? '未提供'} 筆。</p>
      <p>讀取副本處理：{details.json_reader?.normalization === 'UTF8_BOM_REMOVED' ? '僅移除開頭 UTF-8 BOM' : details.json_reader?.normalization === 'NONE' ? '與原始位元組相同' : '未提供'}。</p>
      <p>Hop 保留全空資料列設定紀錄：{details.json_runtime_receipt?.HOP_JSON_INPUT_INCLUDE_NULLS === 'Y' ? '已保存；仍須配合執行及結果比對證據' : '未提供，不能判定已驗證'}。</p>
      <dl><dt>原始檔指紋</dt><dd className="spec-checksum">{details.source_checksum ?? '未提供'}</dd>
        <dt>讀取副本指紋</dt><dd className="spec-checksum">{details.json_reader?.reader_checksum ?? '未提供'}</dd>
        <dt>啟動紀錄指紋</dt><dd className="spec-checksum">{details.json_runtime_receipt?.log_checksum ?? '未提供'}</dd></dl>
    </> : details.source_format === 'XLSX' ? <>
      <ExcelInputSummary value={{contract_status: details.excel_input_contract ? 'CONFIRMED_INPUT_ONLY' : 'MISSING_OR_INVALID', contract: details.excel_input_contract}}/>
      <p>來源完整掃描：{details.excel_structure_validation?.records_expected ?? '未提供'} 筆。</p>
    </> : details.csv_input_contracts ? Object.entries(details.csv_input_contracts).map(([ref, contract]) =>
      csv(contract, details.csv_structure_validations?.[ref], `CSV 來源 ${ref}`))
      : details.csv_input_contract ? csv(details.csv_input_contract, details.csv_structure_validation, 'CSV 來源')
      : <p>此歷史版本沒有可辨識的來源讀取證據；不套用其他格式的規則。</p>}
  </section>;
}
