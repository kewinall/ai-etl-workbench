from pathlib import Path
from io import BytesIO
from uuid import uuid4
import pytest
from openpyxl import Workbook
from app import task_uploads, source_staging
from app.excel_profile import selected_profile
from test_excel_input_contract import policy, workbook


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr(task_uploads, 'ROOT', tmp_path)
    monkeypatch.setattr(task_uploads, 'UPLOAD_ROOT', tmp_path / 'uploads')
    upload = task_uploads.save_and_profile('input.xlsx', workbook())
    selected = selected_profile(upload['upload_id'], upload['checksum'], upload['size'], '明細', 2)
    return {**upload, **selected, 'type': 'EXCEL', 'has_actual_data': True}


def test_single_read_verified_bytes_copy_and_cleanup(source, monkeypatch):
    original = source_staging.read_verified_upload
    reads = []
    def read(*args):
        reads.append(args)
        return original(*args)
    monkeypatch.setattr(source_staging, 'read_verified_upload', read)
    with source_staging.stage_excel_source(uuid4(), source, policy()) as staged:
        directory = staged['directory']
        before = staged['path'].read_bytes()
        Path(source['path']).write_bytes(b'changed original')
        assert staged['path'].read_bytes() == before
        assert staged['evidence']['content_checksum'] == source['checksum']
        assert staged['evidence']['column_types_checked']
        assert not staged['execution_authorized']
    assert len(reads) == 1
    assert not directory.exists()
    assert Path(source['path']).read_bytes() == b'changed original'


def test_selection_mismatch_and_changed_file_rejected(source):
    with pytest.raises(ValueError, match='STAGING_EXCEL_SELECTION_MISMATCH'):
        with source_staging.stage_excel_source(uuid4(), source, dict(policy(), header_row=1)):
            pytest.fail('Unconfirmed selection yielded')
    Path(source['path']).write_bytes(b'changed original')
    with pytest.raises(ValueError):
        with source_staging.stage_excel_source(uuid4(), source, policy()):
            pytest.fail('Changed content yielded')


def test_executor_failure_cleans_only_attempt(source):
    with pytest.raises(RuntimeError):
        with source_staging.stage_excel_source(uuid4(), source, policy()) as staged:
            directory = staged['directory']
            raise RuntimeError('synthetic executor failure')
    assert not directory.exists()
    assert Path(source['path']).exists()


def test_type_error_after_profile_sample_cannot_yield(source):
    book = Workbook()
    sheet = book.active
    sheet.title = '明細'
    sheet.append(['說明'])
    sheet.append(['number'])
    for value in range(21):
        sheet.append([value])
    sheet.append(['not an integer'])
    buffer = BytesIO()
    book.save(buffer)
    book.close()
    upload = task_uploads.save_and_profile('late-error.xlsx', buffer.getvalue())
    selected = selected_profile(upload['upload_id'], upload['checksum'], upload['size'], '明細', 2)
    assert selected['fields'] == [{'name': 'number', 'type': 'BIGINT'}]
    candidate = {**upload, **selected, 'type': 'EXCEL', 'has_actual_data': True}
    with pytest.raises(ValueError, match='EXCEL_NUMBER_TYPE'):
        with source_staging.stage_excel_source(uuid4(), candidate, policy()):
            pytest.fail('Late invalid value yielded execution copy')
    assert Path(upload['path']).exists()
