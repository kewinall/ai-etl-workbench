"""Read-only reconstruction of authorized historical compiler bytes and log counters."""
from hashlib import sha256
from xml.etree import ElementTree as ET
from .delivery_compiler import compile_delivery_components
from .private_log_store import read_private_log
from .hop_log_evidence import hop_log_evidence


def presentation(compiled, binding, run, log=None):
    if (compiled.get('status')!='VALIDATED_NOT_APPROVED'
            or compiled.get('specification_checksum')!=binding.get('specification_checksum')
            or compiled.get('hpl_checksum')!=binding.get('hpl_checksum')):
        raise ValueError('ARTIFACT_EXECUTION_BINDING_CHANGED')
    root=ET.fromstring(compiled['hpl'])
    nodes=[dict(id=n.findtext('name'),component=n.findtext('type')) for n in root.findall('transform')]
    terminal=[e for e in run['events'] if e['event_type'] in
              ('HOP_EXECUTED_QA_REQUIRED','HOP_EXECUTION_FAILED','HOP_RESULT_UNKNOWN')]
    execution=None
    if terminal:
        event=terminal[-1]['event_context']
        if not isinstance(log,bytes) or sha256(log).hexdigest()!=event.get('log_checksum'):
            raise ValueError('ARTIFACT_LOG_BINDING_CHANGED')
        code=event.get('exit_code')
        execution=hop_log_evidence(dict(started=True,reason='EXITED' if type(code) is int else 'UNKNOWN',
                                       exit_code=code,output=log),[n['id'] for n in nodes])
    for node in nodes:
        node['counters']=(execution or {}).get('nodes',{}).get(node['id'])
    return dict(version=1,run_id=str(run['run_id']),scope='HISTORICAL_AUTHORIZED_BYTES_READ_ONLY',
        specification_checksum=compiled['specification_checksum'],hpl_checksum=compiled['hpl_checksum'],
        nodes=nodes,edges=[dict(from_node=h.findtext('from'),to_node=h.findtext('to')) for h in root.findall('./order/hop')],
        plan=compiled['plan'],execution=execution,
        artifacts=[dict(kind=k.upper(),content=compiled[k],checksum=compiled[k+'_checksum']) for k in ('hpl','hwf','ddl')],
        execution_authorized=False,release_ready=False)


def read(queue,task_id,run_id):
    run=queue.detail(task_id,run_id)
    with queue.conn() as conn:
        auth=conn.execute('SELECT * FROM platform.task_run_execution_authorization WHERE run_id=%s',(run_id,)).fetchone()
        if not auth:return dict(status='NO_AUTHORIZED_COMPILER_ARTIFACTS',nodes=[],artifacts=[],execution_authorized=False)
        spec=conn.execute('SELECT * FROM platform.specification WHERE specification_id=%s AND run_id=%s AND task_id=%s',
                          (auth['specification_id'],run_id,task_id)).fetchone()
        if not spec:raise ValueError('ARTIFACT_SPECIFICATION_NOT_FOUND')
        naming=conn.execute('SELECT * FROM platform.naming_contract WHERE contract_id=%s AND task_id=%s',
                            (spec['naming_contract_id'],task_id)).fetchone()
    # These are reconstruction-only compiler preconditions. No stored state or approval is changed.
    snapshot={**run,'matches_current':True,'write_started':False,'state':'NEEDS_REVIEW'}
    compiled=compile_delivery_components(spec['spec_json'],snapshot,naming)
    has_log=any(e['event_type'] in ('HOP_EXECUTED_QA_REQUIRED','HOP_EXECUTION_FAILED','HOP_RESULT_UNKNOWN') for e in run['events'])
    log=read_private_log(queue,task_id,run_id) if has_log else None
    return presentation(compiled,auth['binding'],run,log)
