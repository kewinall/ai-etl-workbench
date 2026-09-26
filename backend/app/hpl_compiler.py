"""Deterministic, portable HPL candidate. Compilation never grants execution rights."""
from hashlib import sha256
from xml.etree.ElementTree import Element, SubElement, tostring, indent

from .etl_specification import compilation_plan, _type


def _values(parent, **values):
    for key, value in values.items():
        SubElement(parent, key).text = str(value) if value is not None else None
    return parent


def compile_hpl(payload, run, naming):
    # Revalidate authoritative snapshots; never accept a pre-labelled VALID plan.
    result = compilation_plan(payload, run, naming)
    if result['status'] != 'VALIDATED_NOT_APPROVED':
        return result
    spec, plan = result['specification'], result['plan']
    root = Element('pipeline')
    info = _values(SubElement(root, 'info'), name='etl_' + result['specification_checksum'][:16],
                   description='Specification ' + result['specification_checksum'] + '; Naming ' + spec['naming']['checksum'])
    parameters = SubElement(info, 'parameters')
    names = ['SOURCE_CSV'] if spec['version'] == 1 else ['SOURCE_CSV_0', 'SOURCE_CSV_1']
    for name in names:
        parameter = SubElement(parameters, 'parameter')
        _values(parameter, name=name, default_value=None, description='Runtime-bound validated CSV; no bundled data')
    order = SubElement(root, 'order')
    edges = [dict(edge) for edge in plan['edges']]
    filter_stages = [stage for stage in plan['stages'] if stage['component'] == 'FilterRows']
    for stage in filter_stages:
        edges.append({'from': stage['id'], 'to': stage.get('discard_id', 'discard')})
    for edge in edges:
        _values(SubElement(order, 'hop'), **{'from': edge['from'], 'to': edge['to'], 'enabled': 'Y'})
    for index, stage in enumerate(plan['stages']):
        node = _values(SubElement(root, 'transform'), name=stage['id'], type=stage['component'], copies=1, distribute='Y')
        _values(SubElement(node, 'GUI'), xloc=80 + index * 180, yloc=100, draw='Y')
        component = stage['component']
        if component == 'CSVInput':
            contract = stage['contract']
            _values(node, filename='${' + stage.get('parameter', 'SOURCE_CSV') + '}', separator=contract['delimiter'], enclosure='"',
                    header='Y' if contract['header'] else 'N', encoding={'UTF-8-SIG': 'UTF-8', 'BIG5': 'Big5'}.get(contract['encoding'], contract['encoding']),
                    lazy_conversion='N', parallel='N', newline_possible='Y', buffer_size=50000,
                    include_filename='N', add_filename_result='N')
            fields = SubElement(node, 'fields')
            for field in stage['fields']:
                kind = _type(field['data_type'])
                hop_type = {'STRING': 'String', 'INTEGER': 'Integer', 'DECIMAL': 'BigNumber', 'BOOLEAN': 'Boolean', 'DATE': 'Date', 'TIMESTAMP': 'Date'}[kind[0]]
                precision = kind[3] if kind[0] == 'DECIMAL' else -1
                length = kind[2] if kind[0] in ('STRING', 'DECIMAL') else -1
                mask = {'DATE': 'yyyy-MM-dd', 'TIMESTAMP': 'yyyy-MM-dd HH:mm:ss'}.get(kind[0], '')
                _values(SubElement(fields, 'field'), name=field['stream_name'], type=hop_type, format=mask,
                        length=length, precision=precision, trim_type='none', decimal='.', group='', currency='')
        elif component == 'FilterRows':
            next_id = next(edge['to'] for edge in plan['edges'] if edge['from'] == stage['id'])
            _values(node, send_true_to=next_id, send_false_to=stage.get('discard_id', 'discard'))
            condition = _values(SubElement(SubElement(node, 'compare'), 'condition'), negated='N')
            conditions = SubElement(condition, 'conditions')
            for predicate in stage['predicates']:
                if predicate['constant'] is not None:
                    # SQL UNKNOWN (null vs constant) must not pass, including NE.
                    _values(SubElement(conditions, 'condition'), negated='N', operator='AND',
                            leftvalue=predicate['column'], function='IS NOT NULL')
                child = _values(SubElement(conditions, 'condition'), negated='N', operator='AND', leftvalue=predicate['column'],
                                function={'EQ': '=', 'NE': '<>', 'LT': '<', 'LE': '<=', 'GT': '>', 'GE': '>=', 'IS_NULL': 'IS NULL', 'IS_NOT_NULL': 'IS NOT NULL'}[predicate['operator']])
                constant = predicate['constant']
                if constant is not None:
                    text = ('Y' if constant['value'] else 'N') if constant['type'] == 'BOOLEAN' else str(constant['value'])
                    _values(SubElement(child, 'value'), name='constant', type={'INTEGER': 'Integer', 'DECIMAL': 'BigNumber', 'STRING': 'String', 'BOOLEAN': 'Boolean', 'DATE': 'Date'}[constant['type']],
                            text=text, length=-1, precision=-1, isnull='N', mask='yyyy-MM-dd' if constant['type'] == 'DATE' else '')
        elif component == 'SortRows':
            _values(node, directory='${java.io.tmpdir}', sort_prefix='workbench', sort_size=100000, unique_rows='N', compress='N')
            fields = SubElement(node, 'fields')
            for name in stage['columns']:
                _values(SubElement(fields, 'field'), name=name, ascending='Y', case_sensitive='Y', collator_enabled='N', collator_strength=0, presorted='N')
        elif component == 'MergeJoin':
            _values(node, join_type='LEFT OUTER' if stage['join_type'] == 'LEFT' else 'INNER')
            for tag, keys in [('keys_1', stage['left_keys']), ('keys_2', stage['right_keys'])]:
                holder = SubElement(node, tag)
                for key in keys:
                    SubElement(holder, 'key').text = key
            _values(node, transform1=stage['left_transform'], transform2=stage['right_transform'])
        elif component == 'GroupBy':
            _values(node, all_rows='N', give_back_row='N', ignore_aggregate='N', add_linenr='N', directory='${java.io.tmpdir}', prefix='workbench')
            group = SubElement(node, 'group')
            for name in stage['group_by']:
                _values(SubElement(group, 'field'), name=name)
            fields = SubElement(node, 'fields')
            for metric in stage['metrics']:
                _values(SubElement(fields, 'field'), aggregate=metric['output_column'], subject=metric['column'],
                        type={'COUNT_ROWS': 'COUNT_ANY', 'COUNT_NON_NULL': 'COUNT_ALL'}.get(metric['function'], metric['function']), valuefield=None)
        elif component == 'SelectValues':
            fields = _values(SubElement(node, 'fields'), select_unspecified='N')
            for name in stage['columns']:
                _values(SubElement(fields, 'field'), name=name, rename=None, length=-1, precision=-1)
        elif component == 'TableOutput':
            _values(node, connection='etl_target', schema=stage['schema'], table=stage['table'], truncate='N',
                    commit=1000, ignore_errors='N', use_batch='Y', specify_fields='Y', partitioning_enabled='N', tablename_in_field='N', return_keys='N')
            fields = SubElement(node, 'fields')
            for name in spec['output_columns']:
                _values(SubElement(fields, 'field'), stream_name=name, column_name=name)
        else:
            raise ValueError('Unsupported compiler stage')
    for stage in filter_stages:
        discard = _values(SubElement(root, 'transform'), name=stage.get('discard_id', 'discard'), type='Dummy', copies=1, distribute='Y')
        _values(SubElement(discard, 'GUI'), xloc=260, yloc=260, draw='Y')
    indent(root, space='  ')
    xml = tostring(root, encoding='utf-8', xml_declaration=True).decode('utf-8')
    return {**result, 'compiler_status': 'HPL_CANDIDATE_NOT_EXECUTABLE', 'hpl': xml,
            'hpl_checksum': sha256(xml.encode('utf-8')).hexdigest(), 'execution_authorized': False,
            'required_checks': ['CSV_BYTES_AND_EXTRA_COLUMNS_POLICY', 'NATIVE_METADATA_AND_ROW_SEMANTICS',
                                'SPECIFICATION_APPROVAL', 'RUNTIME_CONNECTION_BINDING', 'VERTICA_QA_AND_RELEASE_APPROVAL']}
