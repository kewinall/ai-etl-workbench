from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import json
from zipfile import ZipFile
import pytest
from app.release_bundle import BundleArtifact, MEMBERS, build_bundle_candidate


BINDING = dict(run_id='12345678-1234-1234-1234-123456789abc', specification_checksum='a'*64, naming_checksum='b'*64)


def artifacts():
    # Byte-integrity fixtures only, explicitly not real HPL/HWF/XLSX or portable ETL.
    return [BundleArtifact(kind, kind.encode(), sha256(kind.encode()).hexdigest(), **BINDING) for kind in MEMBERS]


def test_reproducible_exact_members_and_manifest_matches_stored_bytes():
    items = artifacts()
    result = build_bundle_candidate(items, **BINDING)
    assert result == build_bundle_candidate(list(reversed(items)), **BINDING)
    assert result['checksum'] == sha256(result['content']).hexdigest()
    assert not result['qa_passed'] and not result['release_ready']
    with ZipFile(BytesIO(result['content'])) as archive:
        assert archive.namelist() == [*MEMBERS.values(), 'release-manifest.json']
        raw = archive.read('release-manifest.json')
        assert json.loads(raw) == result['manifest']
        assert sha256(raw).hexdigest() == result['manifest_checksum']
        assert result['manifest']['portability'] == 'NOT_VERIFIED'
        for item in result['manifest']['artifacts']:
            data = archive.read(item['name'])
            assert sha256(data).hexdigest() == item['checksum']
            assert len(data) == item['size_bytes']
        assert all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in archive.infolist())
        assert archive.testzip() is None


@pytest.mark.parametrize('change', [
    {'content': b'changed'}, {'checksum': 'C'*64}, {'checksum': 'x'},
    {'content': b''}, {'content': bytearray(b'HPL')},
    {'kind': '../credentials'}, {'kind': 'SDM'},
    {'run_id': 'other'}, {'specification_checksum': 'c'*64}, {'naming_checksum': 'c'*64},
])
def test_reject_changed_bytes_unknown_duplicate_or_mixed_versions(change):
    items = artifacts(); items[0] = replace(items[0], **change)
    with pytest.raises(ValueError): build_bundle_candidate(items, **BINDING)


@pytest.mark.parametrize('items', [[], artifacts()[:-1], artifacts()+artifacts()[:1], [None]*5])
def test_requires_exact_artifact_set(items):
    with pytest.raises(ValueError, match='BUNDLE_REQUIRED_ARTIFACTS'):
        build_bundle_candidate(items, **BINDING)


def test_size_limits_before_packaging(monkeypatch):
    monkeypatch.setattr('app.release_bundle.MAX_MEMBER_BYTES', 2)
    with pytest.raises(ValueError, match='BUNDLE_ARTIFACT_SIZE'):
        build_bundle_candidate(artifacts(), **BINDING)
    monkeypatch.setattr('app.release_bundle.MAX_MEMBER_BYTES', 100)
    monkeypatch.setattr('app.release_bundle.MAX_BUNDLE_BYTES', 5)
    with pytest.raises(ValueError, match='BUNDLE_TOTAL_SIZE'):
        build_bundle_candidate(artifacts(), **BINDING)
