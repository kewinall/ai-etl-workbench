// Display guard only. Server validation/checksums remain authoritative.
export function validateSdmExcel(document: any) {
  if (document.version !== 4) return;
  const policy = document.excel_input_contract, reference = document.excel_source;
  if (document.source_format !== 'XLSX' || document.source_ref !== 'source.0' || !policy ||
      policy.version !== 1 || policy.engine !== 'POI' || typeof policy.worksheet !== 'string' ||
      !policy.worksheet.length || policy.worksheet.length > 31 || !Number.isInteger(policy.header_row) ||
      policy.header_row < 1 || policy.header_row > 1000 || !['SKIP','PRESERVE'].includes(policy.blank_rows) ||
      policy.missing_cells !== 'NULL' || policy.extra_columns !== 'REJECT' || policy.formulas !== 'REJECT' ||
      policy.trim_strings !== 'NONE' || policy.on_error !== 'FAIL' || !reference ||
      !['content_checksum','profile_checksum','contract_checksum'].every(key => /^[a-f0-9]{64}$/.test(reference[key] || '')))
    throw new Error('SDM Excel 來源指紋或讀取契約不完整，請重新核對規格。');
}
