"""Path-free confirmed JSON semantics, preserving input and profile versions."""
from copy import deepcopy
import re
from uuid import UUID
from .json_input_contract import JsonInputContractV1, contract_checksum


def validated_json_contract(config):
    sources = config.get('sources') or []
    if len(sources) != 1 or sources[0].get('type') != 'JSON' or sources[0].get('has_actual_data') is not True:
        raise ValueError('JSON_SOURCE_SCOPE_UNSUPPORTED')
    if any(key in config for key in ('csv_input_contract_v1', 'csv_input_contracts_v1', 'excel_input_contract_v1')):
        raise ValueError('JSON_CONTRACT_FORMS_CONFLICT')
    policy = JsonInputContractV1.model_validate(config.get('json_input_contract_v1')).model_dump()
    source = sources[0]
    binding = source.get('json_profile_binding_v1')
    try:
        valid_id = str(UUID(source.get('upload_id'))) == source['upload_id']
    except (ValueError, TypeError, AttributeError):
        valid_id = False
    if (not valid_id or not isinstance(binding, dict)
            or not isinstance(source.get('checksum'), str) or not re.fullmatch('[a-f0-9]{64}', source['checksum'])
            or type(source.get('size')) is not int or not 0 < source['size'] <= 50 * 1024 * 1024
            or not isinstance(source.get('fields'), list) or not 0 < len(source['fields']) <= 200
            or any(not isinstance(field, dict) or not isinstance(field.get('name'), str)
                   or not field['name'].strip() or not isinstance(field.get('type'), str) for field in source['fields'])
            or len({field['name'] for field in source['fields']}) != len(source['fields'])
            or source.get('root_shape') != policy['root_shape']
            or type(binding.get('row_count')) is not int or not 1 <= binding['row_count'] <= 100000):
        raise ValueError('JSON_PROFILE_BINDING_INVALID')
    expected = {'version': 1, 'upload_id': source['upload_id'], 'content_checksum': source['checksum'],
                'byte_count': source['size'], 'fields': source['fields'], 'root_shape': policy['root_shape'],
                'row_count': binding['row_count'], 'profile_version': 1}
    if contract_checksum(binding) != contract_checksum({**expected, 'profile_checksum': contract_checksum(expected),
                                                       'scope': 'INPUT_PROFILE_ONLY'}):
        raise ValueError('JSON_PROFILE_BINDING_CHANGED')
    return {'contract': policy, 'reference': {'content_checksum': source['checksum'],
            'profile_checksum': binding['profile_checksum'], 'contract_checksum': contract_checksum(policy)}}


def json_contract_issues(snapshot):
    config = snapshot.get('source_config') or {}
    if (snapshot.get('source_type') != 'JSON' and 'json_input_contract_v1' not in config
            and not any(source.get('type') == 'JSON' for source in config.get('sources') or [])):
        return []
    try:
        validated_json_contract(config)
    except ValueError:
        return [{'issue_type': 'MISSING' if 'json_input_contract_v1' not in config else 'CONFLICT',
                 'field_path': 'source_config.json_input_contract_v1',
                 'message': '請確認 JSON 檔案結構、缺值與 BOM 處理；契約須與已確認來源版本一致',
                 'suggestion': {'required': True}}]
    return []


def json_evidence(config):
    if not any(source.get('type') == 'JSON' for source in config.get('sources') or []):
        return None
    try:
        return {'source_ref': 'source.0', 'contract_status': 'CONFIRMED_INPUT_ONLY', **validated_json_contract(config)}
    except ValueError:
        return {'source_ref': 'source.0', 'contract_status': 'MISSING_OR_INVALID'}


def json_profile_offer(config):
    sources = config.get('sources') or []
    if len(sources) != 1 or sources[0].get('type') != 'JSON' or not sources[0].get('json_profile_binding_v1'):
        return None
    return {'root_shape': sources[0].get('root_shape'),
            'row_count': sources[0]['json_profile_binding_v1'].get('row_count')}


def revise_json_contract(config, changes):
    result = deepcopy(config)
    if changes is None:
        return result
    result['json_input_contract_v1'] = JsonInputContractV1.model_validate(changes).model_dump()
    validated_json_contract(result)
    return result
