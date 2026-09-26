from hashlib import sha256
import json
import pytest
from app.execution_diagnosis import diagnose


def test_allowlisted_diagnosis_never_leaks_log_values():
    content=b'ERROR: Column "secret_column" does not exist\npassword=never-publish host=private-host\n'
    result=diagnose(content,sha256(content).hexdigest(),'run-id')
    assert result['findings'][0]['code']=='COLUMN_NOT_FOUND'
    assert result['findings'][0]['line_numbers']==[1]
    assert result['role']=='DETERMINISTIC_DIAGNOSTIC'
    assert not result['database_mutation_allowed'] and not result['automatic_retry_allowed']
    assert not any(value in json.dumps(result) for value in ('secret_column','never-publish','private-host'))


def test_unknown_log_is_not_fabricated_root_cause():
    content=b'Unexpected failure'
    assert diagnose(content,sha256(content).hexdigest(),'r')['findings']==[]


def test_changed_log_rejected():
    with pytest.raises(ValueError,match='BINDING_CHANGED'):diagnose(b'changed','0'*64,'r')
