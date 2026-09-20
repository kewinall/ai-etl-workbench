"""Archive integrity fixtures, not evidence of a real Hop or model execution."""
from hashlib import sha256
import pytest
from app.release_bundle import build_bundle_candidate,MEMBERS
from app.formal_release_bundle import build_formal_bundle,candidate_parts
from app.release_portability import validate_portability
from app.sa_contract import digest
from test_release_bundle import artifacts,BINDING


def test_formal_archive_preserves_executable_bytes_and_is_reproducible():
    candidate=build_bundle_candidate(artifacts(),**BINDING)
    binding={**BINDING,'candidate_checksum':candidate['checksum']}
    final=build_formal_bundle(candidate['content'],candidate['manifest'],b'approved SDM fixture',binding)
    assert final==build_formal_bundle(candidate['content'],candidate['manifest'],b'approved SDM fixture',binding)
    before=candidate_parts(candidate['content'],candidate['manifest'])
    after=candidate_parts(final['content'],final['manifest'])
    for kind,name in MEMBERS.items():
        assert (before[name]==after[name]) == (kind!='SDM')
    assert final['manifest']['approval_binding_checksum']==digest(binding)
    assert final['checksum']==sha256(final['content']).hexdigest()
    assert candidate['manifest']['status']=='CANDIDATE_NOT_RELEASED'


def proof_fixture():
    candidate=build_bundle_candidate(artifacts(),**BINDING)
    evidence=dict(version=1,candidate_checksum=candidate['checksum'],source_checksum='d'*64,
        hop_log_checksum='e'*64,result_expected_checksum='f'*64,result_actual_checksum='f'*64,
        expected_count=1,actual_count=1,exit_code=0,isolated_target_created=True,
        original_artifacts_unmodified=True,workflow_completed=True)
    for item in candidate['manifest']['artifacts']:
        if item['type'] in ('HPL','HWF','DDL'):evidence[item['type'].lower()+'_checksum']=item['checksum']
    return candidate,dict(status='PASS',evidence=evidence,checksum=digest(evidence))


def test_portability_requires_trusted_oracle_not_merely_matching_results():
    candidate,row=proof_fixture()
    assert validate_portability(row,candidate,'d'*64,expected_checksum='f'*64,expected_count=1)
    for expected in [dict(expected_checksum='0'*64,expected_count=1),dict(expected_checksum='f'*64,expected_count=2)]:
        with pytest.raises(ValueError,match='RESULT_MISMATCH'):
            validate_portability(row,candidate,'d'*64,**expected)


@pytest.mark.parametrize('field,value', [('status','FAIL'),('checksum','0'*64)])
def test_failed_or_altered_proof_cannot_release(field,value):
    candidate,row=proof_fixture();row[field]=value
    with pytest.raises(ValueError):validate_portability(row,candidate,'d'*64,expected_checksum='f'*64,expected_count=1)


def test_mismatched_candidate_manifest_rejected():
    candidate=build_bundle_candidate(artifacts(),**BINDING)
    with pytest.raises(ValueError,match='MANIFEST_CHANGED'):
        candidate_parts(candidate['content'],{**candidate['manifest'],'status':'RELEASE_READY'})
