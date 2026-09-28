"""Check persisted input intent against the checksum-bound compiled mapping.

No inference from results/oracles, model output, or user-supplied PASS labels.
The QA loader separately reconstructs HPL and verifies the executed checksum.
"""
from .etl_specification import EtlSpecificationV1, EtlSpecificationV2, EtlSpecificationV3, EtlSpecificationV4, EtlSpecificationV5
from .transformation_contract import validate_intent


def check_intent(contract, specification, plan):
    model = EtlSpecificationV5 if specification.get('version') == 5 else EtlSpecificationV4 if specification.get('version') == 4 else EtlSpecificationV3 if specification.get('version') == 3 else EtlSpecificationV2 if specification.get('version') == 2 else EtlSpecificationV1
    spec = model.model_validate(specification)
    multi = spec.version == 2
    stages = plan.get('stages') or []
    sources = [stage for stage in stages if stage.get('component') == ('JsonInput' if spec.version == 5 else 'ExcelInput' if spec.version == 4 else 'CSVInput')]
    if len(sources) != (2 if multi else 1) or plan.get('naming_checksum') != specification['naming']['checksum']:
        raise ValueError('QA_TRANSFORMATION_MAPPING_INVALID')
    columns, source_items = [], []
    for index, stage in enumerate(sources):
        if stage.get('source_ref', 'source.0') != f'source.{index}' or not stage.get('fields'):
            raise ValueError('QA_TRANSFORMATION_MAPPING_INVALID')
        fields = []
        for field in stage['fields']:
            if any(not isinstance(field.get(key), str) or not field[key] for key in ('source_name', 'stream_name', 'data_type')):
                raise ValueError('QA_TRANSFORMATION_MAPPING_INVALID')
            original = field['source_name']
            fields.append({'name': original})
            columns.append({'source_name': f'source.{index}.{original}' if multi else original,
                            'english_name': field['stream_name']})
        source_items.append({'fields': fields})
    for stage in stages:
        if stage.get('component') == 'GroupBy':
            for metric in stage.get('metrics') or []:
                if not isinstance(metric.get('id'), str) or not isinstance(metric.get('output_column'), str):
                    raise ValueError('QA_TRANSFORMATION_MAPPING_INVALID')
                columns.append({'source_name': '$metric.' + metric['id'], 'english_name': metric['output_column']})
    if len({c['source_name'] for c in columns}) != len(columns) or len({c['english_name'] for c in columns}) != len(columns):
        raise ValueError('QA_TRANSFORMATION_MAPPING_INVALID')
    snapshot = {'source_config': {'sources': source_items}, 'target_config': {'transformation_contract_v1': contract}}
    if spec.version==3:
        ordinal=spec.source_order.ordinal_column
        if sources[0].get('ordinal_column')!=ordinal or any(c['english_name']==ordinal for c in columns):
            raise ValueError('QA_TRANSFORMATION_MAPPING_INVALID')
        columns.append({'source_name':'$source_order.source.0','english_name':ordinal})
        snapshot['target_config']['source_order_v1']=spec.source_order.model_dump()
    if validate_intent(spec, snapshot, {'contract_json': {'columns': columns}}):
        raise ValueError('QA_TRANSFORMATION_INTENT_MISMATCH')
