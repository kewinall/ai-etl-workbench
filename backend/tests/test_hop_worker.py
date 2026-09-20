from contextlib import contextmanager
from hashlib import sha256
from unittest.mock import Mock
import pytest
from app import hop_worker


@pytest.fixture
def setup(tmp_path,monkeypatch):
    source,hpl=tmp_path/'source.csv',tmp_path/'candidate.hpl'
    source.write_bytes(b'id\n1\n');hpl.write_bytes(b'<pipeline/>')
    prepared={'directory':tmp_path,'source_path':source,'hpl_path':hpl,
              'binding':{'source_checksum':sha256(source.read_bytes()).hexdigest(),'hpl_checksum':sha256(hpl.read_bytes()).hexdigest()}}
    @contextmanager
    def prepare(*args):yield prepared
    monkeypatch.setattr(hop_worker,'prepare_approved_source',prepare)
    reservation=Mock(return_value={'lease_token':'lease'})
    monkeypatch.setattr(hop_worker,'reserve',reservation)
    queue=Mock()
    queue.complete_hop.side_effect=lambda run,token,result: {'status':result['status']}
    queue.fail_hop_preparation.return_value={'status':'HOP_PREPARATION_INVALID'}
    return queue,prepared,reservation


def test_success_is_submitted_once(setup):
    queue,prepared,reservation=setup
    executor=Mock(return_value={'status':'COMPLETED','exit_code':0,'errors':0,'log_checksum':'a'*64})
    assert hop_worker.execute_once(queue,'task','run','spec','auth',executor)=={'status':'COMPLETED'}
    executor.assert_called_once()
    queue.begin_external_write.assert_called_once_with('run','lease',prepared['binding'])
    queue.complete_hop.assert_called_once()


@pytest.mark.parametrize('invalid', [False,True])
def test_exception_or_invalid_output_is_unknown_without_retry(setup,invalid):
    queue,prepared,reservation=setup
    executor=Mock(return_value={'secret':'must not persist'}) if invalid else Mock(side_effect=RuntimeError('private secret'))
    assert hop_worker.execute_once(queue,'task','run','spec','auth',executor)=={'status':'UNKNOWN'}
    executor.assert_called_once()
    assert queue.complete_hop.call_args.args[2]=={'status':'UNKNOWN','exit_code':None,'errors':None,'log_checksum':None}


def test_mutation_after_reservation_prevents_start(setup):
    queue,prepared,reservation=setup
    def reserve(*args):
        prepared['source_path'].write_bytes(b'changed')
        return {'lease_token':'lease'}
    reservation.side_effect=reserve
    executor=Mock()
    assert hop_worker.execute_once(queue,'task','run','spec','auth',executor)['status']=='HOP_PREPARATION_INVALID'
    queue.fail_hop_preparation.assert_called_once_with('run','lease')
    queue.begin_external_write.assert_not_called()
    executor.assert_not_called()


def test_lease_loss_during_execution_prevents_result_commit(setup):
    queue,prepared,reservation=setup
    def execute(prepared,lost,log_sink):
        lost.set()
        return {'status':'COMPLETED','exit_code':0,'errors':0,'log_checksum':'a'*64}
    assert hop_worker.execute_once(queue,'task','run','spec','auth',execute)['status']=='LEASE_LOST'
    queue.complete_hop.assert_not_called()


def test_missing_adapter_does_not_consume_consent(setup):
    queue,prepared,reservation=setup
    with pytest.raises(ValueError,match='HOP_ADAPTER_REQUIRED'):
        hop_worker.execute_once(queue,'task','run','spec','auth',None)
    reservation.assert_not_called()


def test_adapter_preflight_failure_does_not_consume_consent_or_start_write(setup):
    queue,prepared,reservation=setup
    executor=Mock()
    executor.preflight.side_effect=ValueError('PRE_EXECUTION_TARGET_CLAIM_REQUIRED')
    with pytest.raises(ValueError,match='PRE_EXECUTION_TARGET_CLAIM_REQUIRED'):
        hop_worker.execute_once(queue,'task','run','spec','auth',executor)
    reservation.assert_not_called()
    queue.begin_external_write.assert_not_called()
    executor.assert_not_called()
