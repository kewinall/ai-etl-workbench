from contextlib import nullcontext
from copy import deepcopy
from hashlib import sha256
from uuid import uuid4
import pytest
from app.source_binding import source_set_checksum
from app.prepared_integrity import verify_prepared_files
from app.hop_command import hop_command
from app import execution_preparation
from test_multi_csv import uploaded


@pytest.fixture
def prepared(tmp_path):
    paths = {}; hashes = {}
    for index in range(2):
        folder = tmp_path / f'source-{index}'
        folder.mkdir()
        path = folder / 'source.csv'
        data = f'id\n{index}\n'.encode()
        path.write_bytes(data)
        paths[f'source.{index}'] = path
        hashes[f'source.{index}'] = sha256(data).hexdigest()
    hpl = tmp_path / 'candidate.hpl'
    hpl.write_bytes(b'<pipeline/>')
    return {'directory':tmp_path, 'source_paths': paths, 'hpl_path':hpl,
        'binding':{'source_checksums':hashes, 'source_checksum':source_set_checksum(hashes),
                   'hpl_checksum':sha256(hpl.read_bytes()).hexdigest()}}


def test_each_source_and_order_are_bound_without_private_paths(prepared):
    assert verify_prepared_files(prepared) == prepared['binding']
    hashes = prepared['binding']['source_checksums']
    assert source_set_checksum(dict(reversed(list(hashes.items())))) == source_set_checksum(hashes)
    assert source_set_checksum({'source.0':hashes['source.1'], 'source.1':hashes['source.0']}) != source_set_checksum(hashes)


@pytest.mark.parametrize('ref', ['source.0','source.1'])
@pytest.mark.parametrize('change', ['modify','delete','redirect','directory','missing_binding','wrong_hash'])
def test_neither_source_can_change_or_disappear(prepared, ref, change):
    path = prepared['source_paths'][ref]
    if change == 'modify': path.write_bytes(b'changed')
    elif change == 'delete': path.unlink()
    elif change == 'redirect': prepared['source_paths'][ref] = prepared['source_paths']['source.1' if ref == 'source.0' else 'source.0']
    elif change == 'directory': path.unlink(); path.mkdir()
    elif change == 'missing_binding': del prepared['binding']['source_checksums'][ref]
    else: prepared['binding']['source_checksums'][ref] = 'f'*64
    with pytest.raises(ValueError, match='PREPARED_FILES_CHANGED_OR_UNAVAILABLE'):
        verify_prepared_files(prepared)


def test_no_singular_and_plural_ambiguity(prepared):
    prepared['source_path'] = prepared['source_paths']['source.0']
    with pytest.raises(ValueError, match='PREPARED_FILES_CHANGED_OR_UNAVAILABLE'):
        verify_prepared_files(prepared)


@pytest.mark.parametrize('count', [0,3,True,'2'])
def test_command_does_not_infer_source_count(count):
    with pytest.raises(ValueError, match='INVALID_HOP_SOURCE_COUNT'):
        hop_command('/private/attempt', source_count=count)


def test_fixed_multisource_parameters_no_user_options():
    command = hop_command('/private/attempt with space', source_count=2, credential_launcher=True)
    assert command[-1] == '--parameters=SOURCE_CSV_0=/private/attempt with space/source-0/source.csv;SOURCE_CSV_1=/private/attempt with space/source-1/source.csv'
    assert '--parameters-separator=;' in command
    assert not any('PASSWORD' in arg for arg in command)


@pytest.mark.parametrize('invalidate', [False, True])
def test_preparation_stages_all_bytes_rechecks_approval_and_cleans(uploaded, monkeypatch, invalidate):
    # Storage is a stub here; this tests actual file handling and recheck order,
    # not database authorization. Existing PostgreSQL tests cover V1 storage.
    hpl = '<pipeline/>'
    run_id = uuid4()
    candidate = {'approval_id':'approved', 'specification_checksum':'c'*64,
        'run':{'input_snapshot':{'source_config':uploaded}, 'input_checksum':'a'*64, 'settings_snapshot':{'checksum':'b'*64}},
        'compiled':{'specification':{'version':2}, 'hpl':hpl, 'hpl_checksum':sha256(hpl.encode()).hexdigest()}}
    calls = []
    def load(*args):
        calls.append(1)
        if invalidate and len(calls) == 2:
            return {**candidate, 'approval_id':'changed'}
        return deepcopy(candidate)
    monkeypatch.setattr(execution_preparation,'load_approved_candidate',load)
    class Queue:
        def conn(self): return nullcontext(None)
    from app import task_uploads
    if invalidate:
        with pytest.raises(ValueError,match='PREPARATION_CHANGED'):
            with execution_preparation.prepare_approved_source(Queue(),'task',run_id,uuid4()):
                pytest.fail('Stale approval must not yield')
    else:
        with execution_preparation.prepare_approved_source(Queue(),'task',run_id,uuid4()) as output:
            assert len(output['source_paths']) == 2
            assert output['binding']['source_checksums'] == {f'source.{i}':s['checksum'] for i,s in enumerate(uploaded['sources'])}
            assert verify_prepared_files(output)['source_checksum'] == output['binding']['source_checksum']
            assert not output['execution_authorized']
    assert len(calls) == 2
    assert list((task_uploads.ROOT/'runtime-temp'/'run-sources').iterdir()) == []
