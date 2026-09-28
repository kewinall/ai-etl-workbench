"""Independently inspect the three-node JSON reader contract; no ETL replay."""
import json
from .json_input_contract import JsonInputContractV1
from .etl_specification import _type


def expected_json_source(stage):
    policy = JsonInputContractV1.model_validate(stage['contract'])
    fields = []
    for field in stage['fields']:
        kind = _type(field['data_type'])
        literal = json.dumps(field['source_name'], ensure_ascii=False).replace('$', '\\u0024')
        fields.append(dict(name=field['stream_name'],
            path=('$.[*]' if policy.root_shape == 'ARRAY' else '$.') + '[' + literal + ']',
            type={'STRING': 'String', 'INTEGER': 'Integer', 'DECIMAL': 'BigNumber',
                  'BOOLEAN': 'Boolean', 'DATE': 'Date', 'TIMESTAMP': 'Date'}[kind[0]],
            length=str(kind[2] if kind[0] in ('STRING', 'DECIMAL') else -1),
            precision=str(kind[3] if kind[0] == 'DECIMAL' else -1),
            format={'DATE': 'yyyy-MM-dd', 'TIMESTAMP': 'yyyy-MM-dd HH:mm:ss'}.get(kind[0], ''),
            decimal='.', group='', currency='', trim_type='none', repeat='N'))
    return dict(node_id=stage['id'], source_ref=stage['source_ref'], component='JsonInput',
        options=dict(include='N', rownum='N', addresultfile='N', readurl='N',
            IsIgnoreEmptyFile='N', doNotFailIfNoFile='N', ignoreMissingPath='N',
            defaultPathLeafToNull='Y', limit='0', IsInFields='Y', IsAFile='Y',
            valueField='json_source_file', removeSourceField='N'), fields=fields,
        filename=dict(node_id='source_file', component='RowGenerator', limit='1', never_ending='N',
            field=dict(name='json_source_file', type='String', nullif='${SOURCE_JSON}', length='-1', precision='-1', set_empty_string='N')),
        projection=dict(node_id='source_columns', component='SelectValues', select_unspecified='N',
            fields=[dict(name=f['stream_name'], rename=f['stream_name'], length='-2', precision='-2') for f in stage['fields']]),
        launcher_requirement={'HOP_JSON_INPUT_INCLUDE_NULLS': 'Y', 'receipt_required': True})


def validate_json_stages(plan):
    stages = plan['stages']
    sources = [s for s in stages if s['component'] in ('JsonInput', 'CSVInput', 'ExcelInput')]
    if (len(stages) < 4 or len(sources) != 1 or sources[0]['component'] != 'JsonInput'
            or stages[0] != dict(id='source_file', component='RowGenerator', purpose='SINGLE_FILENAME_PARAMETER', parameter='SOURCE_JSON')
            or stages[1] != sources[0] or sources[0]['id'] != 'source' or sources[0].get('source_ref') != 'source.0'
            or stages[2] != dict(id='source_columns', component='SelectValues', columns=[f['stream_name'] for f in sources[0]['fields']])
            or plan['edges'][:2] != [{'from': 'source_file', 'to': 'source'}, {'from': 'source', 'to': 'source_columns'}]):
        raise ValueError('QA_RUNTIME_JSON_PLAN_CHANGED')


def _leaves(node, expected, allowed=()):
    if node is None or set(child.tag for child in node) != set(expected) | set(allowed):
        raise ValueError('QA_RUNTIME_JSON_OPTIONS_CHANGED')
    for key, value in expected.items():
        found = node.findall(key)
        if len(found) != 1 or len(found[0]) or (found[0].text or '') != value:
            raise ValueError('QA_RUNTIME_JSON_OPTIONS_CHANGED')
    if any(len(node.findall(tag)) != 1 for tag in allowed):
        raise ValueError('QA_RUNTIME_JSON_OPTIONS_CHANGED')


def inspect_json_source(root, expected):
    def node(name, component, options):
        found = [n for n in root.findall('transform') if n.findtext('name') == name]
        if len(found) != 1:
            raise ValueError('QA_RUNTIME_JSON_SOURCE_CHANGED')
        result = found[0]
        _leaves(result, dict(name=name, type=component, copies='1', distribute='Y', **options), ('fields', 'GUI'))
        return result
    filename, projection = expected['filename'], expected['projection']
    f = node(filename['node_id'], filename['component'], {k: filename[k] for k in ('limit', 'never_ending')})
    holder = f.find('fields')
    if len(holder) != 1 or holder[0].tag != 'field': raise ValueError('QA_RUNTIME_JSON_FILENAME_CHANGED')
    _leaves(holder[0], filename['field'])
    reader = node(expected['node_id'], 'JsonInput', expected['options'])
    holder = reader.find('fields')
    if [child.tag for child in holder] != ['field'] * len(expected['fields']): raise ValueError('QA_RUNTIME_JSON_FIELDS_CHANGED')
    for actual, wanted in zip(holder, expected['fields']): _leaves(actual, wanted)
    p = node(projection['node_id'], projection['component'], {})
    holder = p.find('fields')
    if (len(holder.findall('select_unspecified')) != 1 or holder.findtext('select_unspecified') != 'N'
            or [child.tag for child in holder] != ['select_unspecified'] + ['field'] * len(projection['fields'])):
        raise ValueError('QA_RUNTIME_JSON_PROJECTION_CHANGED')
    for actual, wanted in zip(holder.findall('field'), projection['fields']): _leaves(actual, wanted)
    hops = root.findall('./order/hop')
    related = [h for h in hops if h.findtext('from') in ('source_file', 'source') or h.findtext('to') in ('source', 'source_columns')]
    if len(related) != 2: raise ValueError('QA_RUNTIME_JSON_HOPS_CHANGED')
    for actual, wanted in zip(related, [dict(from_='source_file', to='source'), dict(from_='source', to='source_columns')]):
        _leaves(actual, {'from': wanted['from_'], 'to': wanted['to'], 'enabled': 'Y'})


def json_behavior_reference():
    return dict(scope='SEPARATE_ENGINE_PROBES_NOT_THIS_RUN_OR_RUNTIME_VERSION_ATTESTATION',
        engines='Apache Hop 2.12.0', evidence_document='docs/verification/json-execution-binding-2026-09-28.md',
        native_json_test='test_json_hop_cli_native.py',
        observations=['Native JSON CLI separately verified required files, empty-object preservation and filter/aggregation node counts.',
            'Typed whole-file preflight and BOM-only reader copy retain both fingerprints; no implicit CSV conversion.'],
        limits='Separate synthetic probes, not this Run, Vertica acceptance, exhaustive parser testing or rollback guarantee.')
