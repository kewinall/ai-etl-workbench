"""Fixed single-pipeline workflow. No loops, retries, SQL or execution grant."""
from hashlib import sha256
from xml.etree.ElementTree import Element, SubElement, indent, tostring
from .hpl_compiler import compile_hpl, _values


def compile_hwf(payload, run, naming):
    compiled = compile_hpl(payload, run, naming)
    if 'hpl' not in compiled:
        return compiled
    root = Element('workflow')
    _values(root, name='etl_' + compiled['specification_checksum'][:16],
            description='HPL SHA-256: ' + compiled['hpl_checksum'], name_sync_with_filename='N')
    parameters = SubElement(root, 'parameters')
    names = ('SOURCE_CSV_0', 'SOURCE_CSV_1') if compiled['specification']['version'] == 2 else ('SOURCE_CSV',)
    for name in names:
        parameter = SubElement(parameters, 'parameter')
        _values(parameter, name=name, default_value=None,
                description='Runtime-bound validated CSV; no bundled data')
    actions = SubElement(root, 'actions')
    start = SubElement(actions, 'action')
    _values(start, name='Start', type='SPECIAL', repeat='N', schedulerType=0,
            parallel='N', xloc=80, yloc=100)
    pipeline = SubElement(actions, 'action')
    _values(pipeline, name='Run pipeline', type='PIPELINE',
            filename='${Internal.Workflow.Filename.Folder}/pipeline.hpl',
            run_configuration='local', wait_until_finished='Y',
            exec_per_row='N', params_from_previous='N', parallel='N',
            set_logfile='N', clear_rows='N', clear_files='N', xloc=260, yloc=100)
    _values(SubElement(pipeline, 'parameters'), pass_all_parameters='Y')
    hop = SubElement(SubElement(root, 'hops'), 'hop')
    _values(hop, **{'from': 'Start', 'to': 'Run pipeline', 'enabled': 'Y',
                   'evaluation': 'Y', 'unconditional': 'Y'})
    indent(root, space='  ')
    xml = tostring(root, encoding='utf-8', xml_declaration=True).decode('utf-8')
    return {**compiled, 'compiler_status': 'HWF_CANDIDATE_NOT_EXECUTABLE',
            'hwf': xml, 'hwf_checksum': sha256(xml.encode()).hexdigest(),
            'execution_authorized': False}
