"""Worker-only byte evidence from the approved input snapshot; never ETL."""
from .upload_integrity import read_verified_upload


def source_preflight(snapshot):
    # CSV checksum helpers currently depend on SA's deterministic Gate contract.
    # Load after Worker initialization to avoid that existing import cycle.
    from .csv_content_validation import validate_csv_content
    config = snapshot.get('source_config') or {}
    evidence, issues = [], []
    for index, source in enumerate(config.get('sources') or []):
        if not (source.get('has_actual_data') or source.get('upload_id') or source.get('path')):
            continue
        if source.get('type') not in ('CSV', 'EXCEL', 'JSON'):
            continue
        item = {'source_ref': f'source.{index}', 'execution_authorized': False}
        try:
            content = read_verified_upload(source.get('upload_id'), source.get('type'),
                                           source.get('checksum'), source.get('size'))
            item.update(status='UPLOAD_BYTES_VERIFIED', content_checksum=source['checksum'],
                        byte_count=len(content))
            if source['type'] == 'CSV':
                item['csv'] = validate_csv_content(content, config.get('csv_input_contract_v1'),
                                                   [field.get('name') for field in source.get('fields', [])])
                if item['csv']['status'] == 'INVALID':
                    item['status'] = 'CSV_CONTENT_INVALID'
        except ValueError as error:
            item['status'] = str(error)
        if item['status'] != 'UPLOAD_BYTES_VERIFIED':
            issues.append(dict(issue_type='CONFLICT', field_path=f'source_config.sources.{index}',
                               message='來源檔案未通過版本或內容檢查，請重新上傳並確認來源設定',
                               suggestion={'required': True, 'code': item['status']}))
        evidence.append(item)
    return evidence, issues
