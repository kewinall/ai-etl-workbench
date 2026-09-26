from copy import deepcopy
import pytest
from app.release_portability import validate_portability
from app.source_binding import source_set_checksum
from app.sa_contract import digest
from test_formal_release_bundle import proof_fixture


@pytest.mark.parametrize('change', [None,'swap','missing','legacy','aggregate'])
def test_portability_proof_binds_both_sources_and_refuses_legacy(change):
    candidate,row = proof_fixture()
    checksums = {'source.0':'a'*64,'source.1':'b'*64}
    aggregate = source_set_checksum(checksums)
    row['evidence'].update(version=2,source_checksum=aggregate,source_checksums=deepcopy(checksums))
    if change == 'swap': row['evidence']['source_checksums'] = {'source.0':'b'*64,'source.1':'a'*64}
    if change == 'missing': row['evidence']['source_checksums'].pop('source.1')
    if change == 'legacy':
        row['evidence']['version'] = 1
        row['evidence'].pop('source_checksums')
    if change == 'aggregate': aggregate = '0'*64
    row['checksum'] = digest(row['evidence'])
    def check():
        return validate_portability(row,candidate,aggregate,expected_checksum='f'*64,
                                    expected_count=1,source_checksums=checksums)
    if change:
        with pytest.raises(ValueError): check()
    else:
        assert check()['source_checksums'] == checksums
