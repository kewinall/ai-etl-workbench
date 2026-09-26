from copy import deepcopy
import pytest
from app.source_binding import execution_sources, expected_prepared_binding, source_set_checksum


def sources():
    return {'sources': [{'type': 'CSV', 'upload_id': str(i), 'checksum': char*64}
                        for i,char in enumerate(('a', 'b'))]}


def test_sources_are_ordered_complete_and_single_source_compatible():
    config = sources()
    binding = execution_sources(config, 2)
    assert binding == {'source_checksums': {'source.0': 'a'*64, 'source.1': 'b'*64},
                       'source_checksum': source_set_checksum({'source.0': 'a'*64, 'source.1': 'b'*64})}
    config['sources'].reverse()
    assert execution_sources(config, 2)['source_checksum'] != binding['source_checksum']
    assert execution_sources({'sources': config['sources'][:1]}, 1) == {'source_checksum': 'b'*64}


@pytest.mark.parametrize('change', ['missing', 'extra', 'type', 'upload', 'checksum', 'version'])
def test_partial_or_unverified_sources_are_not_bound(change):
    config = sources(); version = 2
    if change == 'missing': config['sources'].pop()
    if change == 'extra': config['sources'].append(deepcopy(config['sources'][0]))
    if change == 'type': config['sources'][1]['type'] = 'TABLE'
    if change == 'upload': config['sources'][1].pop('upload_id')
    if change == 'checksum': config['sources'][1]['checksum'] = 'invalid'
    if change == 'version': version = 2.0
    with pytest.raises(ValueError): execution_sources(config, version)


def test_expected_prepared_binding_keeps_both_hashes_and_detects_aggregate_tamper():
    binding = dict(run_id='run', specification_id='spec', specification_checksum='c'*64,
                   input_checksum='d'*64, settings_checksum='e'*64, hpl_checksum='f'*64,
                   specification_approval_id='approval', **execution_sources(sources(), 2))
    expected = expected_prepared_binding(binding)
    assert expected['source_checksums'] == binding['source_checksums']
    assert expected['approval_id'] == 'approval' and 'specification_approval_id' not in expected
    expected['source_checksums']['source.1'] = '0'*64
    assert binding['source_checksums']['source.1'] == 'b'*64
    binding['source_checksum'] = '0'*64
    with pytest.raises(ValueError): expected_prepared_binding(binding)
