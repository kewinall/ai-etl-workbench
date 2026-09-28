// Display guard only; authoritative validation remains server-side.
export function validateSdmJson(document: any) {
  if (document.version !== 5) return;
  const policy = document.json_input_contract, reference = document.json_source;
  const fixed: Record<string, unknown> = {version: 1, encoding: 'UTF-8-SIG',
    bom_handling: 'REMOVE_UTF8_BOM', missing_keys: 'NULL', extra_keys: 'REJECT',
    nested_values: 'REJECT', duplicate_keys: 'REJECT', trim_strings: 'NONE',
    null_records: 'PRESERVE', on_error: 'FAIL'};
  if (document.source_format !== 'JSON' || document.source_ref !== 'source.0' ||
      !policy || !['ARRAY', 'OBJECT'].includes(policy.root_shape) ||
      !Object.entries(fixed).every(([key, value]) => policy[key] === value) ||
      Object.keys(policy).length !== Object.keys(fixed).length + 1 || !reference ||
      Object.keys(reference).length !== 3 ||
      !['content_checksum', 'profile_checksum', 'contract_checksum'].every(key =>
        typeof reference[key] === 'string' && /^[a-f0-9]{64}$/.test(reference[key])))
    throw new Error('SDM JSON 來源指紋或讀取契約不完整，請重新核對規格。');
}
