import pytest
from app.execution_oracle import required_result_query_checksum


@pytest.mark.parametrize('binding', [None, [], {}, {'result_query_checksum': None},
    {'result_query_checksum': 'a'*63}, {'result_query_checksum': 'A'*64},
    {'result_query_checksum': 'a'*64+'\n'}, {'result_query_checksum': True}])
def test_missing_or_malformed_legacy_query_binding_is_not_inferred(binding):
    with pytest.raises(ValueError, match='EXECUTION_RESULT_QUERY_BINDING_REQUIRED'):
        required_result_query_checksum(binding)


def test_exact_query_binding_returned_without_mutation():
    binding = {'result_query_checksum': 'a'*64}
    assert required_result_query_checksum(binding) == 'a'*64
    assert binding == {'result_query_checksum': 'a'*64}
