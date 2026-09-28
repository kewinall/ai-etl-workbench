"""JSON original/reader lineage: path-free binding, never execution permission."""
from copy import deepcopy
import re


def reader_binding(evidence, reference):
    value = {'version': 1, 'reader_checksum': evidence['reader_content_checksum'],
             'original_byte_count': evidence['byte_count'], 'reader_byte_count': evidence['reader_byte_count'],
             'normalization': evidence['normalization'],
             'profile_checksum': reference['profile_checksum'], 'contract_checksum': reference['contract_checksum']}
    result = {'source_format': 'JSON', 'source_checksum': reference['content_checksum'], 'json_reader': value}
    if evidence['content_checksum'] != result['source_checksum'] or evidence['contract_checksum'] != value['contract_checksum']:
        raise ValueError('JSON_READER_BINDING_INVALID')
    validate_reader_binding(result)
    return result


def validate_reader_binding(binding):
    value = binding.get('json_reader')
    if (binding.get('source_format') != 'JSON' or 'source_checksums' in binding
            or not isinstance(value, dict) or set(value) != {'version', 'reader_checksum', 'original_byte_count',
                'reader_byte_count', 'normalization', 'profile_checksum', 'contract_checksum'}
            or type(value['version']) is not int or value['version'] != 1
            or any(not isinstance(item, str) or not re.fullmatch('[a-f0-9]{64}', item) for item in
                   (binding.get('source_checksum'), value['reader_checksum'], value['profile_checksum'], value['contract_checksum']))
            or any(type(value[key]) is not int or not 0 < value[key] <= 50 * 1024 * 1024
                   for key in ('original_byte_count', 'reader_byte_count'))):
        raise ValueError('JSON_READER_BINDING_INVALID')
    delta = value['original_byte_count'] - value['reader_byte_count']
    if not ((value['normalization'] == 'NONE' and delta == 0 and value['reader_checksum'] == binding['source_checksum'])
            or (value['normalization'] == 'UTF8_BOM_REMOVED' and delta == 3 and value['reader_checksum'] != binding['source_checksum'])):
        raise ValueError('JSON_READER_BINDING_INVALID')
    return deepcopy(value)


def execution_binding(config):
    from .json_contract_binding import validated_json_contract
    from .upload_integrity import read_verified_upload
    from .json_source_profile import verify_json_source
    from .json_input_contract import prepare_json_reader_content
    bound = validated_json_contract(config)
    source = config['sources'][0]
    content = read_verified_upload(source['upload_id'], 'JSON', source['checksum'], source['size'])
    verify_json_source(source, content=content)
    _, evidence = prepare_json_reader_content(content, bound['contract'], [f['name'] for f in source['fields']],
                                              column_types=[f['type'] for f in source['fields']])
    return reader_binding(evidence, bound['reference'])
