"""Compiler and same-source evidence for QA; no model, SQL or ETL execution."""
from .csv_content_validation import validate_csv_content
from .upload_integrity import read_verified_upload


def execution_details(run, compiled, authorization):
    config=run['input_snapshot']['source_config']
    sources=config.get('sources') or []
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
