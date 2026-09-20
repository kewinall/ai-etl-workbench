from uuid import uuid4
import pytest
from app import task_uploads
from app.source_staging import stage_csv_source

CONTRACT = {'version':1,'encoding':'UTF-8','delimiter':',','header':True,'extra_columns':'REJECT'}


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr(task_uploads, 'ROOT', tmp_path)
    monkeypatch.setattr(task_uploads, 'UPLOAD_ROOT', tmp_path / 'uploads')
    return {**task_uploads.save_and_profile('input.csv', b'id\n1\n'), 'type':'CSV'}


def test_attempt_copy_is_independent_and_cleaned(source):
    from pathlib import Path
    with stage_csv_source(uuid4(), source, CONTRACT) as staged:
        Path(source['path']).write_bytes(b'id\n2\n')
        assert staged['path'].read_bytes() == b'id\n1\n'
        assert staged['evidence']['content_checksum'] == source['checksum']
        assert not staged['execution_authorized']
        directory = staged['directory']
    assert not directory.exists()
    assert Path(source['path']).read_bytes() == b'id\n2\n'


def test_attempts_do_not_overwrite_each_other(source):
    run = uuid4()
    with stage_csv_source(run, source, CONTRACT) as first:
        with stage_csv_source(run, source, CONTRACT) as second:
            assert first['directory'] != second['directory']
        assert first['path'].exists()


def test_failure_cleans_only_attempt(source):
    with pytest.raises(RuntimeError):
        with stage_csv_source(uuid4(), source, CONTRACT) as staged:
            directory = staged['directory']
            raise RuntimeError('synthetic executor failure')
    assert not directory.exists()
    with pytest.raises(ValueError, match='STAGING_CSV_INVALID'):
        with stage_csv_source(uuid4(), {**source,'fields':[{'name':'different','type':'BIGINT'}]}, CONTRACT) as staged:
            pytest.fail('Invalid CSV must not yield')
