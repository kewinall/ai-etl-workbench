"""Cross-bind JSON source, reader and saved runtime receipt, never QA approval."""
import re
from .json_input_contract import contract_checksum
from .json_execution_binding import reader_binding, validate_reader_binding
from .qa_json_options import validate_json_stages


def validate_json_details(spec, details, checks):
    reference, validation, contract = spec['json_source'], details['json_structure_validation'], details['json_input_contract']
    validate_reader_binding(details)
    plan = details['compiler_plan']
    validate_json_stages(plan)
    source = plan['stages'][1]
    if (details['source_format'] != 'JSON' or details['json_source'] != reference
            or details['source_checksum'] != reference['content_checksum']
            or contract_checksum(contract) != reference['contract_checksum']
            or validation.get('status') != 'JSON_STRUCTURE_VALIDATED_NOT_EXECUTABLE'
            or validation.get('complete') is not True or validation.get('column_types_checked') is not True
            or validation.get('type_conversion_verified') is not False or validation.get('execution_authorized') is not False
            or validation.get('root_shape') != contract['root_shape'] or source['contract'] != contract
            or validation.get('field_names_checksum') != contract_checksum([f['source_name'] for f in source['fields']])
            or type(validation.get('records_expected')) is not int or not 1 <= validation['records_expected'] <= 100000
            or not isinstance(validation.get('column_types_checksum'), str)
            or not re.fullmatch('[a-f0-9]{64}', validation['column_types_checksum'])
            or reader_binding(validation, reference) != {key: details[key] for key in ('source_format', 'source_checksum', 'json_reader')}):
        raise ValueError('QA_JSON_DETAILS_BINDING_CHANGED')
    expected = {'version': 1, 'scope': 'PRIVATE_LAUNCHER_SYSTEM_PROPERTY_RECEIPT',
                'HOP_JSON_INPUT_INCLUDE_NULLS': 'Y', 'qa_passed': False,
                'log_checksum': checks['hop_execution']['checksum']}
    if (type(details['json_runtime_receipt'].get('version')) is not int
            or details['json_runtime_receipt'].get('qa_passed') is not False
            or details['json_runtime_receipt'] != expected):
        raise ValueError('QA_JSON_RUNTIME_RECEIPT_CHANGED')
