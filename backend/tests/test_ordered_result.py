import pytest

from app.expected_result import ResultColumn as C, compare_ordered_result


COLUMNS = [C('source_row_number', 'INTEGER'), C('record_id', 'INTEGER')]
ROWS = [{'source_row_number': 1, 'record_id': 30},
        {'source_row_number': 2, 'record_id': 10},
        {'source_row_number': 3, 'record_id': 30}]


def compare(expected, actual, columns=COLUMNS):
    return compare_ordered_result(columns, expected, actual,
                                  ordinal_column='source_row_number')


def test_source_order_is_not_record_id_order_and_duplicates_are_preserved():
    result = compare(ROWS, ROWS)
    assert result['status'] == 'MATCH'
    assert result['expected_checksum'] == result['actual_checksum']
    assert result['qa_passed'] is result['release_ready'] is False
    assert compare(ROWS, sorted(ROWS, key=lambda r: r['record_id']))['status'] == 'MISMATCH'


def test_same_multiset_reversed_fails_without_sorting_away_defect():
    result = compare(ROWS, list(reversed(ROWS)))
    assert result['status'] == 'MISMATCH'
    assert result['missing_count'] == result['unexpected_count'] == 0
    assert result['position_mismatch_count'] == 2
    assert result['expected_checksum'] != result['actual_checksum']


def test_missing_duplicate_and_wrong_ordinal_fail():
    for actual in (ROWS[:-1], ROWS + ROWS[:1],
                   [{**ROWS[0], 'source_row_number': 2}, *ROWS[1:]]):
        assert compare(ROWS, actual)['status'] == 'MISMATCH'


def test_invalid_frozen_sequence_rejected():
    with pytest.raises(ValueError, match='RESULT_EXPECTED_SOURCE_ORDER_INVALID'):
        compare(list(reversed(ROWS)), ROWS)


@pytest.mark.parametrize('columns', [
    [C('record_id', 'INTEGER')],
    [C('source_row_number', 'INTEGER', True), C('record_id', 'INTEGER')],
    [C('source_row_number', 'TEXT'), C('record_id', 'INTEGER')],
])
def test_invalid_order_contract_rejected_even_when_empty(columns):
    with pytest.raises(ValueError, match='RESULT_ORDER_COLUMN_INVALID'):
        compare([], [], columns)


def test_empty_output_is_not_release_approval():
    result = compare([], [])
    assert result['status'] == 'MATCH'
    assert result['release_ready'] is False
