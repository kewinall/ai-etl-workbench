"""Compiler and same-source evidence for QA; no model, SQL or ETL execution."""
from .csv_content_validation import validate_csv_content
from .upload_integrity import read_verified_upload
from .source_binding import execution_sources
from .csv_contract import source_csv_contract


def execution_details(run, compiled, authorization):
    config=run['input_snapshot']['source_config']
    sources=config.get('sources') or []
    if compiled['specification']['version'] == 2:
        binding = execution_sources(config, 2)
        if (any(authorization.get(key) != value for key, value in binding.items())
                or compiled['hpl_checksum'] != authorization.get('hpl_checksum')):
            raise ValueError('QA_EXECUTED_SOURCE_BINDING_CHANGED')
        contracts, validations = {}, {}
        for i, source in enumerate(sources):
            ref = f'source.{i}'
            contract = source_csv_contract(config, ref)
            content = read_verified_upload(source['upload_id'], 'CSV', source['checksum'], source['size'])
            result = validate_csv_content(content, contract, [field['name'] for field in source['fields']])
            if result['status'] != 'CSV_STRUCTURE_VALIDATED_NOT_EXECUTABLE' or not result['complete']:
                raise ValueError('QA_EXECUTED_CSV_NO_LONGER_VERIFIABLE')
            contracts[ref], validations[ref] = contract, result
        return dict(csv_input_contracts=contracts, csv_structure_validations=validations, **binding,
            compiler_plan=compiled['plan'], output_types=compiled['output_types'], hpl_checksum=compiled['hpl_checksum'],
            validation_scope='SAME_EXECUTED_BYTES_RECHECKED_NO_ETL_REPLAY',
            extra_columns_enforcement='WHOLE_BATCH_VALIDATION_BEFORE_HOP')
    if len(sources)!=1 or sources[0].get('type')!='CSV':
        raise ValueError('QA_SINGLE_CSV_EVIDENCE_REQUIRED')
    source=sources[0]
    if (source.get('checksum')!=authorization.get('source_checksum')
            or compiled['hpl_checksum']!=authorization.get('hpl_checksum')):
        raise ValueError('QA_EXECUTED_SOURCE_BINDING_CHANGED')
    content=read_verified_upload(source['upload_id'],'CSV',source['checksum'],source['size'])
    contract=config['csv_input_contract_v1']
    result=validate_csv_content(content,contract,[field['name'] for field in source['fields']])
    if result['status']!='CSV_STRUCTURE_VALIDATED_NOT_EXECUTABLE' or not result['complete']:
        raise ValueError('QA_EXECUTED_CSV_NO_LONGER_VERIFIABLE')
    return dict(csv_input_contract=contract,compiler_plan=compiled['plan'],
        output_types=compiled['output_types'],hpl_checksum=compiled['hpl_checksum'],
        source_checksum=source['checksum'],csv_structure_validation=result,
        validation_scope='SAME_EXECUTED_BYTES_RECHECKED_NO_ETL_REPLAY',
        extra_columns_enforcement='WHOLE_BATCH_VALIDATION_BEFORE_HOP')
