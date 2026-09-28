"""Pure binding of confirmed XLSX read semantics; no paths, reads or authority."""
from hashlib import sha256
import json
import re
from .excel_input_contract import ExcelInputContractV1


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validated_excel_contract(config):
    sources = config.get('sources') or []
    if len(sources) != 1 or sources[0].get('type') != 'EXCEL' or sources[0].get('has_actual_data') is not True:
        raise ValueError('EXCEL_SOURCE_SCOPE_UNSUPPORTED')
    if 'csv_input_contract_v1' in config or 'csv_input_contracts_v1' in config:
        raise ValueError('EXCEL_CONTRACT_FORMS_CONFLICT')
    policy = ExcelInputContractV1.model_validate(config.get('excel_input_contract_v1')).model_dump()
    source = sources[0]
    selected = source.get('excel_selection_v1')
    if not isinstance(selected, dict) or type(selected.get('version')) is not int:
        raise ValueError('EXCEL_SELECTION_REQUIRED')
    expected = {'version': 1, 'upload_id': source.get('upload_id'), 'content_checksum': source.get('checksum'),
                'byte_count': source.get('size'), 'worksheet': policy['worksheet'], 'header_row': policy['header_row'],
                'fields': source.get('fields'), 'sample_limit': 20}
    if (not isinstance(source.get('checksum'), str) or not re.fullmatch(r'[a-f0-9]{64}', source['checksum'])
            or type(source.get('size')) is not int or not 0 < source['size'] <= 50 * 1024 * 1024
            or not source.get('upload_id') or not source.get('fields') or len(source['fields']) > 200
            or (source.get('worksheet'), source.get('header_row')) != (policy['worksheet'], policy['header_row'])
            or selected != {**expected, 'profile_checksum': digest(expected), 'scope': 'INPUT_SELECTION_ONLY'}):
        raise ValueError('EXCEL_SELECTION_BINDING_MISMATCH')
    return {'contract': policy, 'reference': {'content_checksum': source['checksum'],
            'profile_checksum': selected['profile_checksum'], 'contract_checksum': digest(policy)}}


def excel_contract_issues(snapshot):
    config = snapshot.get('source_config') or {}
    if (snapshot.get('source_type') != 'EXCEL' and 'excel_input_contract_v1' not in config
            and not any(source.get('type') == 'EXCEL' for source in config.get('sources') or [])):
        return []
    try:
        validated_excel_contract(config)
    except ValueError:
        return [{'issue_type': 'MISSING' if 'excel_input_contract_v1' not in config else 'CONFLICT',
                 'field_path': 'source_config.excel_input_contract_v1',
                 'message': '請確認 Excel 工作表、標頭列、空白列與型別政策；讀取契約須與已確認檔案版本一致',
                 'suggestion': {'required': True}}]
    return []


def excel_evidence(config):
    if not any(source.get('type') == 'EXCEL' for source in config.get('sources') or []):
        return None
    try:
        bound = validated_excel_contract(config)
    except ValueError:
        return {'source_ref': 'source.0', 'contract_status': 'MISSING_OR_INVALID'}
    return {'source_ref': 'source.0', 'contract_status': 'CONFIRMED_INPUT_ONLY', **bound}
