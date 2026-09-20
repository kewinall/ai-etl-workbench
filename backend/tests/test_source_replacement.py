from copy import deepcopy
import pytest
from app import task_uploads
from app.source_replacement import replace_csv_source, verify_csv_replacement


def test_replacement_preserves_old_file_and_rejects_changed_new_file(tmp_path, monkeypatch):
    monkeypatch.setattr(task_uploads, 'UPLOAD_ROOT', tmp_path)
    old = task_uploads.save_and_profile('old.csv', b'id\n1\n')
    new = task_uploads.save_and_profile('new.csv', b'id\n2\n')
    config = {'sources':[{**old,'type':'CSV','has_actual_data':True}], 'csv_input_contract_v1':{'version':1}}
    before = deepcopy(config)
    replacement = {key:new[key] for key in ('upload_id','checksum','size','original_name','fields')}
    result = replace_csv_source(config, replacement)
    verify_csv_replacement(replacement)
    assert config == before
    assert result['sources'][0]['upload_id'] == new['upload_id']
    assert result['csv_input_contract_v1'] == {'version':1}
    assert (tmp_path / old['upload_id'] / 'source.csv').read_bytes() == b'id\n1\n'
    (tmp_path / new['upload_id'] / 'source.csv').write_bytes(b'id\n3\n')
    with pytest.raises(ValueError, match='UPLOAD_CONTENT_CHANGED'):
        verify_csv_replacement(replacement)
    with pytest.raises(ValueError):
        replace_csv_source(config, {**replacement, 'path':'untrusted'})
    with pytest.raises(ValueError, match='CSV_REPLACEMENT_UNSUPPORTED_METADATA'):
        replace_csv_source({**config, 'query':'must not discard silently'}, replacement)


def test_no_replacement_preserves_all_existing_metadata():
    source = {'sources':[{'type':'CSV','password':'private'}], 'custom':'preserved'}
    assert replace_csv_source(source, None) == source
