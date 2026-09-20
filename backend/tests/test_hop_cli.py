from hashlib import sha256
from threading import Event
from unittest.mock import Mock
import pytest
from app import hop_cli

@pytest.fixture
def setup(tmp_path,monkeypatch):
    prepared={'directory':tmp_path,'source_path':tmp_path/'source.csv','hpl_path':tmp_path/'candidate.hpl','binding':{}}
    for key,checksum in [('source_path','source_checksum'),('hpl_path','hpl_checksum')]:
        prepared[key].write_bytes(b'synthetic');prepared['binding'][checksum]=sha256(b'synthetic').hexdigest()
    (tmp_path/'metadata.json').write_bytes(b'{}')
    monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED','true')
    monkeypatch.setattr(hop_cli,'hop_command',Mock(return_value=['/opt/hop/hop-run.sh']))
    process=Mock(return_value={'started':True,'reason':'EXITED','exit_code':0,'output':b'2026/09/13 05:29:11 - target.0 - Finished processing (I=0, O=0, R=3, W=3, U=0, E=0)\n'})
    monkeypatch.setattr(hop_cli,'run_managed',process)
    options=dict(metadata_checksum=sha256(b'{}').hexdigest(),expected_nodes=['target'],environment={},
                 log_sink=lambda data:{'checksum':sha256(data).hexdigest(),'size':len(data)})
    return prepared,process,options

def test_result_requires_saved_log_and_contains_no_raw_output(setup):
    prepared,process,options=setup
    result=hop_cli.run_hop_cli(prepared,Event(),**options)
    assert result['result']['status']=='COMPLETED'
    assert 'output' not in result and 'directory' not in result
    process.assert_called_once()
    hop_cli.hop_command.assert_called_once_with(prepared['directory'].as_posix(),credential_launcher=False)

def test_credential_environment_selects_launcher_without_secret_in_arguments(setup):
    prepared,process,options=setup
    options['environment']={'WORKBENCH_VERTICA_PASSWORD':'synthetic-only'}
    hop_cli.run_hop_cli(prepared,Event(),**options)
    hop_cli.hop_command.assert_called_once_with(prepared['directory'].as_posix(),credential_launcher=True)
    assert 'synthetic-only' not in repr(process.call_args.args)

def test_metadata_change_prevents_process_start(setup):
    prepared,process,options=setup
    (prepared['directory']/'metadata.json').write_bytes(b'changed')
    with pytest.raises(ValueError,match='HOP_METADATA_CHANGED'):hop_cli.run_hop_cli(prepared,Event(),**options)
    process.assert_not_called()

def test_storage_mismatch_cannot_report_success(setup):
    prepared,process,options=setup
    options['log_sink']=lambda data:{'checksum':'0'*64,'size':len(data)}
    with pytest.raises(ValueError,match='HOP_LOG_PERSISTENCE_MISMATCH'):hop_cli.run_hop_cli(prepared,Event(),**options)

def test_execution_disabled_prevents_process_start(setup,monkeypatch):
    prepared,process,options=setup
    monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED','false')
    with pytest.raises(ValueError,match='EXECUTION_DISABLED'):hop_cli.run_hop_cli(prepared,Event(),**options)
    process.assert_not_called()
