"""Opt-in native Hop metadata loading, never starts an engine."""
import os
from pathlib import Path
import subprocess
import pytest
from app.hop_metadata import local_metadata_json, vertica_metadata_json
from test_source_staging_hop import linux_path

pytestmark=pytest.mark.skipif(os.getenv('WORKBENCH_NATIVE_HOP_STAGING_TEST')!='1',reason='Explicit native Hop verification required')


@pytest.mark.parametrize('vertica', [False, True])
def test_python_metadata_loads_in_native_hop(tmp_path, vertica):
    java=Path(__file__).resolve().parents[2]/'scripts'/'hop'
    content = vertica_metadata_json(dict(type='VERTICA',host='synthetic.invalid',database='synthetic',user='synthetic',port=5433,tlsmode='disable')) if vertica else local_metadata_json()
    (tmp_path/'metadata.json').write_text(content,encoding='utf-8')
    verifier = 'InspectVerticaMetadata.java' if vertica else 'VerifyMetadataExport.java'
    result=subprocess.run(['wsl','-d','RockyLinux9','-u','root','--','docker','run','--rm','--pull','never',
        '--network','none','--hostname','hop-validation','--add-host','hop-validation:127.0.0.1',
        '--entrypoint','java','-w','/opt/hop','-v',linux_path(java)+':/validation:ro',
        '-v',linux_path(tmp_path)+':/candidate:ro','apache/hop:2.12.0','-cp',
        'lib/core/*:lib/beam/*:lib/swt/linux/x86_64/*','/validation/'+verifier,'--candidate'],
        capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    expected = 'VERTICA_METADATA_ROUNDTRIP_PASSED connection=false execution=false' if vertica else 'LOCAL_METADATA_ROUNDTRIP_PASSED execution=false database=false'
    assert expected in result.stdout
