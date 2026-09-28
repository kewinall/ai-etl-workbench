"""Cross-bind Excel QA evidence; never substitutes for execution/result checks."""
from .sa_contract import digest


def validate_excel_details(spec, details):
    reference = spec['excel_source']
    validation = details['excel_structure_validation']
    contract = details['excel_input_contract']
    stages = [stage for stage in details['compiler_plan']['stages'] if stage['component'] == 'ExcelInput']
    if (details['source_format'] != 'XLSX' or details['excel_source'] != reference
            or details['source_checksum'] != reference['content_checksum']
            or digest(contract) != reference['contract_checksum']
            or validation.get('content_checksum') != reference['content_checksum']
            or validation.get('contract_checksum') != reference['contract_checksum']
            or validation.get('status') != 'EXCEL_STRUCTURE_VALIDATED_NOT_EXECUTABLE'
            or validation.get('complete') is not True or validation.get('column_types_checked') is not True
            or validation.get('type_conversion_verified') is not False
            or validation.get('execution_authorized') is not False
            or len(stages) != 1 or stages[0].get('contract') != contract
            or stages[0].get('source_ref') != 'source.0'
            or any(stage['component'] == 'CSVInput' for stage in details['compiler_plan']['stages'])):
        raise ValueError('QA_EXCEL_DETAILS_BINDING_CHANGED')
