"""Pure guards for the pending, explicitly scoped partial-commit acceptance.

No dispatch, SQL, process signal, approval, or retry is performed here.
The caller must prove normal website consent and the live owner separately.
"""
from collections import Counter
from hashlib import sha256
import re
from uuid import UUID

PROJECT_ID='346e9419-4b0e-4ba7-ad29-1756ca7da833'
TARGET='ui_accept_partial_20261011_v1'
AUTHORIZATION='authorized-partial-owner-loss-20261011'
ROWS=tuple((i,f'row-{i:04d}') for i in range(1,1002))
SOURCE=('record_key,label\n'+''.join(f'{i},{label}\n' for i,label in ROWS)).encode()
SOURCE_SHA256=sha256(SOURCE).hexdigest()


def check_scope(current,task_id,run_id,binding_checksum,parents_unexecuted=False):
    spec=current['specification'];run=current['run']
    sources=run['input_snapshot']['source_config']['sources']
    if (str(run['project_id'])!=PROJECT_ID or run['task_id']!=task_id
            or str(run['run_id'])!=str(UUID(run_id))
            or not re.fullmatch(r'[a-f0-9]{64}',binding_checksum or '')
            or current['binding_checksum']!=binding_checksum
            or run['write_started'] is not False
            or (run.get('parent_run_id') and parents_unexecuted is not True)
            or spec['version']!=1 or spec['target_schema']!='ai_sample'
            or spec['target_table']!=TARGET or spec['write_mode']!='APPEND'
            or spec['output_columns']!=['record_key','label']
            or spec['filters']!=[] or spec['aggregation'] is not None
            or spec.get('joins') not in (None,[])
            or len(sources)!=1 or sources[0].get('checksum')!=SOURCE_SHA256):
        raise ValueError('PARTIAL_ACCEPTANCE_SCOPE_INVALID')
    return TARGET


def verify_committed_prefix(rows):
    """Fresh-session reads must prove every persisted row, not just COUNT."""
    try:
        valid=len(rows)==1000 and Counter(map(tuple,rows))==Counter(ROWS[:1000])
    except (TypeError,ValueError):
        valid=False
    if not valid:raise ValueError('PARTIAL_COMMITTED_PREFIX_NOT_PROVEN')
    return {'observed_rows':1000,'distinct_keys':1000,'minimum_key':1,
            'maximum_key':1000,'sum_keys':500500,'fixed_prefix_match':True}


def verified_owner(inspect,container_id,task_id,run_id,binding_checksum,nonce,authorization):
    """Reject names, stale handles, other services, and unauthorised termination."""
    if authorization!=AUTHORIZATION:raise ValueError('PARTIAL_TERMINATION_NOT_AUTHORIZED')
    if not re.fullmatch(r'[a-f0-9]{64}',container_id or '') or not re.fullmatch(r'[a-f0-9]{32}',nonce or ''):
        raise ValueError('EXACT_OWNER_HANDLE_REQUIRED')
    labels=inspect.get('Config',{}).get('Labels') or {}
    expected={'workbench.partial.project':PROJECT_ID,'workbench.partial.task':task_id,
              'workbench.partial.run':str(UUID(run_id)),'workbench.partial.binding':binding_checksum,
              'workbench.partial.target':TARGET,'workbench.partial.nonce':nonce,
              'workbench.partial.source':SOURCE_SHA256}
    state=inspect.get('State',{})
    if (not re.fullmatch(r'[a-f0-9]{64}',binding_checksum or '')
            or inspect.get('Id')!=container_id or state.get('Running') is not True
            or state.get('Paused') is not False or state.get('Restarting') is not False
            or type(state.get('Pid')) is not int or state['Pid']<=0
            or any(labels.get(key)!=value for key,value in expected.items())
            or inspect.get('HostConfig',{}).get('RestartPolicy',{}).get('Name')!='no'):
        raise ValueError('LIVE_SCOPED_OWNER_NOT_PROVEN')
    return container_id
