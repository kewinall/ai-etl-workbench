"""Inspect bound native XLSX options; no replay or current-engine attestation."""
from .excel_input_contract import ExcelInputContractV1
from .etl_specification import _type


def expected_excel_source(stage):
    policy = ExcelInputContractV1.model_validate(stage['contract'])
    fields = []
    for field in stage['fields']:
        kind = _type(field['data_type'])
        fields.append(dict(name=field['stream_name'],
            type={'STRING': 'String', 'INTEGER': 'Integer', 'DECIMAL': 'BigNumber',
                  'BOOLEAN': 'Boolean', 'DATE': 'Date', 'TIMESTAMP': 'Date'}[kind[0]],
            length=str(kind[2] if kind[0] in ('STRING', 'DECIMAL') else -1),
            precision=str(kind[3] if kind[0] == 'DECIMAL' else -1),
            format={'DATE': 'yyyy-MM-dd', 'TIMESTAMP': 'yyyy-MM-dd HH:mm:ss'}.get(kind[0], ''),
            trim_type='none', repeat='N', decimal='.', group='', currency=''))
    return dict(node_id=stage['id'], source_ref=stage.get('source_ref', 'source.0'), component='ExcelInput',
        options=dict(spreadsheet_type='POI', header='Y', noempty='Y' if policy.blank_rows == 'SKIP' else 'N',
            stoponempty='N', strict_types='N', error_ignored='N', error_line_skipped='N',
            accept_filenames='N', add_to_result_filenames='N', limit='0'),
        file=dict(name='${SOURCE_XLSX}', filemask='', exclude_filemask='', file_required='Y', include_subfolders='N'),
        sheet=dict(name=policy.worksheet, startrow=str(policy.header_row - 1), startcol='0'), fields=fields)


def inspect_excel_source(node, expected):
    if (node is None or node.findtext('type') != 'ExcelInput'
            or any(node.findtext(key) != value for key, value in expected['options'].items())):
        raise ValueError('QA_RUNTIME_EXCEL_OPTIONS_CHANGED')
    files, sheets = node.findall('file'), node.findall('./sheets/sheet')
    if (len(files) != 1 or len(sheets) != 1 or node.findall('./files/file')
            or {key: files[0].findtext(key) for key in expected['file']} != expected['file']
            or {key: sheets[0].findtext(key) for key in expected['sheet']} != expected['sheet']):
        raise ValueError('QA_RUNTIME_EXCEL_SELECTION_CHANGED')
    keys = ('name', 'type', 'length', 'precision', 'format', 'trim_type', 'repeat', 'decimal', 'group', 'currency')
    fields = [{key: field.findtext(key) for key in keys} for field in node.findall('./fields/field')]
    if fields != expected['fields']:
        raise ValueError('QA_RUNTIME_EXCEL_FIELDS_CHANGED')


def excel_behavior_reference():
    return dict(scope='SEPARATE_ENGINE_PROBES_NOT_THIS_RUN_OR_RUNTIME_VERSION_ATTESTATION',
        engines='Apache Hop 2.12.0', evidence_document='docs/verification/excel-typed-staging-2026-09-28.md',
        native_excel_test='test_excel_input_native.py',
        observations=['POI ExcelInput separately verified blank-row SKIP/PRESERVE, text precision, nulls, dates, booleans and whitespace.',
            'Full selected-sheet validation rejects formulas, extra columns and incompatible values before Hop; it does not assert engine conversion success.'],
        limits='Separate synthetic reader probes, not this Run, current runtime version attestation, Vertica acceptance or proof of rollback of committed batches.')
