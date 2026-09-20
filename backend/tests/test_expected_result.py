from decimal import Decimal, localcontext
import json
import pytest
from app.expected_result import ResultColumn as C, compare_expected_result as compare


def test_order_independent_exact_decimal_and_duplicate_multiplicity():
    columns=[C('name','TEXT'),C('amount','DECIMAL')]
    a={'name':'A','amount':Decimal('301.350')}
    b={'name':'B','amount':Decimal('300')}
    result=compare(columns,[a,a,b],[b,{**a,'amount':Decimal('301.35')},a])
    assert result['status']=='MATCH'
    assert result['expected_checksum']==result['actual_checksum']
    assert result['qa_passed'] is result['release_ready'] is False
    result=compare(columns,[a,a,b],[a,b,b])
    assert result['status']=='MISMATCH'
    assert result['expected_count']==result['actual_count']==3
    assert result['missing_count']==result['unexpected_count']==1


def test_decimal_comparison_does_not_round_under_low_precision():
    with localcontext() as context:
        context.prec=2
        result=compare([C('amount','DECIMAL')],[{'amount':Decimal('123456789.123456789')}],
                       [{'amount':Decimal('123456789.123456788')}])
    assert result['status']=='MISMATCH'


def test_null_empty_case_and_whitespace_are_distinct_and_no_values_in_evidence():
    columns=[C('name','TEXT',True)]
    result=compare(columns,[{'name':None},{'name':' private customer '}],[{'name':''},{'name':'PRIVATE CUSTOMER'}])
    assert result['missing_count']==result['unexpected_count']==2
    assert 'customer' not in json.dumps(result).lower()


@pytest.mark.parametrize('column,value',[(C('n','INTEGER'),True),(C('n','INTEGER'),'1'),
    (C('n','INTEGER'),2**63),(C('n','DECIMAL'),1.1),(C('n','DECIMAL'),Decimal('NaN')),
    (C('n','DECIMAL'),Decimal('1E+99999')),(C('n','TEXT'),None),(C('n','BOOLEAN'),1)])
def test_invalid_types_fail_without_coercion(column,value):
    with pytest.raises(ValueError,match='RESULT_'):
        compare([column],[],[{'n':value}])


@pytest.mark.parametrize('rows',[[{'other':1}],[{'n':1,'extra':2}],[{}],({'n':1} for _ in range(2))])
def test_schema_or_unbounded_input_rejected(rows):
    with pytest.raises(ValueError,match='RESULT_'):compare([C('n','INTEGER')],[],rows)


def test_empty_is_a_comparison_not_successful_execution():
    result=compare([C('n','INTEGER')],[],[])
    assert result['status']=='MATCH'
    assert result['qa_passed'] is False
    with pytest.raises(ValueError,match='RESULT_INVALID_COLUMNS'):compare([C('n','INTEGER'),C('n','TEXT')],[],[])


def test_content_budget_counts_duplicates_and_both_sides(monkeypatch):
    import app.expected_result as module
    monkeypatch.setattr(module,'MAX_CANONICAL_BYTES',32)
    row={'n':'abc'}
    assert compare([C('n','TEXT')],[row],[row])['status']=='MATCH'
    for expected,actual in [([row]*3,[]),([],[row]*3)]:
        with pytest.raises(ValueError,match='RESULT_CONTENT_LIMIT_EXCEEDED'):
            compare([C('n','TEXT')],expected,actual)


def test_content_budget_counts_json_unicode_expansion(monkeypatch):
    import app.expected_result as module
    monkeypatch.setattr(module,'MAX_CANONICAL_BYTES',24)
    assert compare([C('n','TEXT')],[{'n':'abc'}],[])['status']=='MISMATCH'
    with pytest.raises(ValueError,match='RESULT_CONTENT_LIMIT_EXCEEDED'):
        compare([C('n','TEXT')],[{'n':'中文名'}],[])


def test_invalid_kind_is_a_validation_error():
    with pytest.raises(ValueError,match='RESULT_INVALID_COLUMNS'):
        compare([C('n',[])],[],[])
