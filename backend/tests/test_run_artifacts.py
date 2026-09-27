from copy import deepcopy
from hashlib import sha256
import json
import pytest
from app.run_artifacts import presentation
from app.delivery_compiler import compile_delivery_components
from test_etl_specification import design


def fixture():
    spec,run,naming=design();c=compile_delivery_components(spec,run,naming)
    binding={k:c[k] for k in ('specification_checksum','hpl_checksum')}
    names=['source','filter','sort','aggregate','projection','target','discard']
    log=('private password=never-expose\n'+''.join(f'WORKBENCH_NODE_V1 {n} 0 0 0 0 0 0\n' for n in names)+'WORKBENCH_METRICS_END_V1 7\n').encode()
    run.update(events=[dict(event_type='HOP_EXECUTED_QA_REQUIRED',event_context=dict(exit_code=0,log_checksum=sha256(log).hexdigest()))])
    return c,binding,run,log


def test_actual_counters_and_artifacts_no_raw_log_or_permissions():
    c,b,r,log=fixture();out=presentation(c,b,r,log)
    assert out['execution']['complete_node_evidence']
    assert out['execution']['result']['status']=='COMPLETED'
    assert all(n['counters']['errors']==0 for n in out['nodes'])
    assert {a['kind'] for a in out['artifacts']}=={'HPL','HWF','DDL'}
    assert not out['execution_authorized'] and not out['release_ready']
    assert 'never-expose' not in json.dumps(out)


def test_failed_and_incomplete_are_not_success_or_zero():
    c,b,r,log=fixture();r['events'][0]['event_context']['exit_code']=1
    assert presentation(c,b,r,log)['execution']['result']['status']=='FAILED'
    log=b'private failure';r['events'][0]['event_context']['log_checksum']=sha256(log).hexdigest()
    out=presentation(c,b,r,log)
    assert not out['execution']['complete_node_evidence']
    assert all(n['counters'] is None for n in out['nodes'])


@pytest.mark.parametrize('key',['hpl_checksum','specification_checksum'])
def test_drift_is_rejected(key):
    c,b,r,log=fixture();b[key]='0'*64
    with pytest.raises(ValueError,match='EXECUTION_BINDING_CHANGED'):presentation(c,b,r,log)


def test_wrong_log_is_rejected():
    c,b,r,log=fixture()
    with pytest.raises(ValueError,match='LOG_BINDING_CHANGED'):presentation(c,b,r,log+b'changed')
