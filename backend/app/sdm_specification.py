"""Deterministic SDM content candidate, not an approved workbook or release."""
from copy import deepcopy
from hashlib import sha256
import json
from .etl_specification import validate_specification


def build_sdm_candidate(payload,run,naming):
    validated=validate_specification(payload,run,naming)
    if validated['status']!='VALIDATED_NOT_APPROVED':
        raise ValueError('SDM_VALID_SPECIFICATION_REQUIRED')
    spec=validated['specification']
    by_name={column['english_name']:column for column in naming['contract_json']['columns']}
    aggregate=spec.get('aggregation')
    metrics={metric['output_column']:metric for metric in aggregate['metrics']} if aggregate else {}
    def source(name):
        column=by_name[name]
        if spec['version'] == 2:
            qualified = column['source_name']
            refs = [ref for ref in spec['source_refs'] if qualified.startswith(ref + '.')]
            if len(refs) != 1:
                raise ValueError('SDM_SOURCE_QUALIFICATION_REQUIRED')
            return {'source_ref': refs[0], 'original_name': qualified[len(refs[0])+1:],
                    'stream_name': name, 'data_type': column['vertica_type']}
        return {'source_ref':spec['source_ref'],'original_name':column['source_name'],
                'stream_name':name,'data_type':column['vertica_type']}
    mappings=[]
    for position,name in enumerate(spec['output_columns'],1):
        metric=metrics.get(name)
        if metric:
            inputs=[source(metric['column'])] if metric['column'] else []
            operation=metric['function']
        else:
            inputs=[source(name)];operation='GROUP_KEY' if aggregate else 'DIRECT'
        mappings.append({'position':position,'target_column':name,
            'target_type':validated['output_types'][name],'operation':operation,'source_columns':inputs,
            'metric_id':metric['id'] if metric else None})
    document={'version':1,'document_type':'SDM_CANDIDATE','run_id':spec['run_id'],
        'specification_checksum':validated['specification_checksum'],
        'naming':deepcopy(spec['naming']),
        **({'source_refs':deepcopy(spec['source_refs']),'joins':deepcopy(spec['joins'])}
           if spec['version'] == 2 else {'source_ref':spec['source_ref']}),
        'target':{'schema':spec['target_schema'],'table':spec['target_table'],'write_mode':spec['write_mode']},
        'mappings':mappings,'filters':deepcopy(spec['filters']),
        'filter_logic':spec['filter_logic'],'filter_null_policy':spec['filter_null_policy'],
        'aggregation':deepcopy(aggregate)}
    if spec['version'] == 2:
        document['version'] = 2
    checksum=sha256(json.dumps(document,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'status':'SDM_CANDIDATE_NOT_RELEASED','document':document,'checksum':checksum,
            'qa_passed':False,'release_ready':False}
