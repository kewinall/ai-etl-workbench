"""Recheck frozen synthetic scenario evidence; never executes or approves a run."""
import json
from hashlib import sha256
from .pilot_fixture_catalog import corpus
from .sa_contract import digest
from .execution_oracle import load_execution_oracle
from .result_oracle import compare_oracle_document

MUTATIONS = {
    'semantic-filter-aggregate': ('filters.0.operator', 'GE', 'GT'),
    'semantic-date-boundaries': ('filters.1.operator', 'LT', 'LE'),
    'semantic-left-join': ('joins.0.join_type', 'LEFT', 'INNER'),
    'semantic-empty-result': ('filters.0.constant.value', 100, 20),
    'semantic-null-group': ('aggregation.metrics.0.function', 'COUNT_ROWS', 'COUNT_NON_NULL'),
}


def ancestors(runs):
    by_id = {str(r['run_id']): r for r in runs}
    result = []; current = runs[-1] if runs else None; seen = set()
    while current:
        key = str(current['run_id'])
        if key in seen: raise ValueError('SCENARIO_LINEAGE_CYCLE')
        seen.add(key); result.append(current)
        parent = current['parent_run_id']
        if parent is not None and str(parent) not in by_id: raise ValueError('SCENARIO_LINEAGE_INCOMPLETE')
        current = by_id.get(str(parent)) if parent is not None else None
    return result


def sources_match(run, fixed):
    expected = fixed['fixture']['sources']
    actual = run['input_snapshot']['source_config']['sources']
    evidence = (run.get('gate_result') or {}).get('source_evidence') or []
    if len(actual) != len(expected): return False
    for index, (source, frozen) in enumerate(zip(actual, expected)):
        checksum = sha256(frozen['content'].encode()).hexdigest()
        if source.get('checksum') != checksum or source.get('fields') != [{'name':n,'type':t} for n,t in frozen['fields']]: return False
        if not any(e.get('source_ref') == f'source.{index}' and e.get('content_checksum') == checksum
                   and e.get('status') == 'UPLOAD_BYTES_VERIFIED' for e in evidence): return False
    return True


def semantic_proof(run, events, case_key):
    if run['write_started'] is not False or any(e['event_type']=='WRITE_STARTED' for e in events): return None
    expected = MUTATIONS[case_key]
    for event in events:
        if event['event_type'] != 'SPECIFICATION_SEMANTIC_REJECTED': continue
        p = event['event_context']; unsigned = {k:v for k,v in p.items() if k!='attempt_checksum'}
        if (digest(unsigned)!=p.get('attempt_checksum') or p.get('input_checksum')!=run['input_checksum']
                or p.get('settings_checksum')!=run['settings_snapshot']['checksum']
                or p.get('specification_saved') is not False or p.get('execution_authorized') is not False): continue
        if any((i.get('field_path'),i.get('expected'),i.get('actual'))==expected
               and i.get('node_id') and i.get('requirement_path') for i in p.get('issues',[])):
            return {'run_id':str(run['run_id']),'event_id':event['event_id'],'checksum':p['attempt_checksum']}
    return None


def gap_proof(run, events, fixed):
    if run['write_started'] is not False or any(e['event_type']=='WRITE_STARTED' for e in events): return None
    change = fixed['fixture']['initial_change']; field=change['field']
    source=run['input_snapshot']['source_config']; target=run['input_snapshot']['target_config']
    if field=='join.keys':
        value=(target.get('join_contract_v1') or {}).get('joins',[{}])[0].get('keys'); path='join_contract_v1'
    elif field.startswith('csv_input_contract_v1.'):
        value=(source.get('csv_input_contract_v1') or {}).get('encoding'); path='source_config.csv_input_contract_v1'
    else:
        value=(target.get('requirements_v1') or {}).get(field.split('.')[-1]); path=field
    gate=run.get('gate_result') or {}
    if value!=change['initial'] or gate.get('status')!='NEEDS_INPUT' or not any(i.get('field_path')==path for i in gate.get('issues',[])): return None
    event=next((e for e in events if e['event_type']=='REQUIREMENT_NEEDS_INPUT'),None)
    return {'run_id':str(run['run_id']),'event_id':event['event_id']} if event else None


def recovery_proof(queue, conn, task, run, events, fixed, latest):
    if run['state']!='FAILED' or run['outcome_code']!='HOP_EXECUTION_FAILED' or not run['write_started']: return None
    observed=[e for e in events if e['event_type']=='SYNTHETIC_FAILURE_TARGET_OBSERVED']
    injected=[e for e in events if e['event_type']=='SYNTHETIC_MISSING_COLUMN_INJECTED']
    failed=[e for e in events if e['event_type']=='HOP_EXECUTION_FAILED']
    if len(observed)!=1 or len(injected)!=1 or len(failed)!=1: return None
    if not injected[0]['event_id'] < failed[0]['event_id'] < observed[0]['event_id']: return None
    p=observed[0]['event_context']; fault=injected[0]['event_context']; f=failed[0]['event_context']
    column=fixed['fixture']['initial_change']['column']; columns=[c[0] for c in fixed['oracle']['columns']];columns[0]=column+'_missing_fault'
    if (digest({k:v for k,v in p.items() if k!='checksum'})!=p.get('checksum')
            or p.get('run_id')!=str(run['run_id']) or p.get('outcome')!='HOP_EXECUTION_FAILED'
            or p.get('engine_stopped') is not True or p.get('columns')!=columns
            or fault.get('case_key')!=fixed['definition']['case_key'] or fault.get('column')!=column
            or fault.get('renamed_to')!=column+'_missing_fault' or fault.get('original_hpl_unchanged') is not True
            or f.get('exit_code')!=1 or not f.get('errors')): return None
    closed=conn.execute('SELECT * FROM platform.execution_reconciliation WHERE run_id=%s',(run['run_id'],)).fetchone()
    if (not closed or closed['evidence_sha256']!=p['checksum'] or closed['observed_row_count']!=p.get('observed_row_count')
            or closed['binding']['input_checksum']!=run['input_checksum']): return None
    if not any(e['event_type']=='OPERATOR_RECONCILED_WITHOUT_RETRY' and e['event_id']>observed[0]['event_id']
               and e['event_context'].get('reconciliation_id')==str(closed['reconciliation_id']) for e in events): return None
    dispatch=conn.execute('SELECT binding_checksum FROM platform.hop_dispatch_request WHERE run_id=%s',(run['run_id'],)).fetchone()
    if not dispatch or dispatch['binding_checksum']!=fault.get('binding_checksum'): return None
    old=run['input_snapshot']['target_config'];new=latest['input_snapshot']['target_config']
    if old.get('schema')!='ai_sample' or new.get('schema')!='ai_sample' or old.get('table')==new.get('table'): return None
    from .execution_diagnosis import diagnose
    from .private_log_store import read_private_log
    diagnosis=diagnose(read_private_log(queue,task,run['run_id']),f['log_checksum'],run['run_id'])
    if not any(i['code']=='COLUMN_NOT_FOUND' and i['line_numbers'] for i in diagnosis['findings']): return None
    return {'run_id':str(run['run_id']),'event_id':failed[0]['event_id'],'checksum':p['checksum']}


def check(queue, case, measured):
    fixed=next((c for c in corpus() if c['definition']==case['definition']),None)
    result={'status':'EVIDENCE_REQUIRED','source_verified':False,'frozen_oracle_verified':False,'precondition':None}
    if not fixed: return {**result,'status':'UNSUPPORTED_CATALOG'}
    if not case['runs'] or not case['attempt_order_verified']: return result
    with queue.conn() as conn:
        task=queue.locked_task(conn,case['task_id'])
        runs=conn.execute('SELECT * FROM platform.task_run WHERE task_id=%s',(case['task_id'],)).fetchall()
        by_id={str(r['run_id']):r for r in runs}
        ordered=[by_id[str(r['run_id'])] for r in case['runs']]
        chain=ancestors(ordered);latest=chain[0]
        if not queue.matches_current(conn,task,latest): return {**result,'status':'INPUT_OR_SETTINGS_CHANGED'}
        result['source_verified']=sources_match(latest,fixed)
        for prior in chain[1:]:
            events=conn.execute('SELECT event_id,event_type,event_context FROM platform.task_run_event WHERE run_id=%s ORDER BY event_id',(prior['run_id'],)).fetchall()
            scenario=fixed['definition']['scenario']
            if scenario in ('SEMANTIC_DEFECT','EXECUTION_RECOVERY') and not sources_match(prior,fixed): continue
            proof=(semantic_proof(prior,events,case['case_key']) if scenario=='SEMANTIC_DEFECT' else
                   gap_proof(prior,events,fixed) if scenario=='REQUIREMENT_GAP' else
                   recovery_proof(queue,conn,case['task_id'],prior,events,fixed,latest) if scenario=='EXECUTION_RECOVERY' else None)
            if proof: result['precondition']=proof;break
        if fixed['definition']['scenario']=='SUCCESS': result['precondition']={'kind':'NO_FAULT_REQUIRED'}
        if latest['outcome_code']=='HOP_EXECUTED_QA_REQUIRED':
            pinned=load_execution_oracle(queue,case['task_id'],latest['run_id'],connection=conn)
            document=json.loads(pinned['content']);o=fixed['oracle']
            expected_columns=[{'name':n,'kind':'INTEGER' if t=='BIGINT' else 'TEXT','nullable':True} for n,t in o['columns']]
            rows=[dict(zip([c[0] for c in o['columns']],values)) for values in o['rows']]
            compared=compare_oracle_document(pinned['content'],rows,document_checksum=pinned['document_checksum'],
                specification_checksum=document['specification_checksum'],naming_checksum=document['naming_checksum'])
            result['frozen_oracle_verified']=document['columns']==expected_columns and compared['status']=='MATCH'
        if all((result['source_verified'],result['frozen_oracle_verified'],result['precondition'],measured['status']=='RELEASE_READY')):
            result['status']='SCENARIO_EVIDENCE_MATCHED'
    return result
