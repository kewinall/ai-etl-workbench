from hashlib import sha256
import pytest
from app.csv_content_validation import validate_csv_content


def check(data, **changes):
    contract = dict(version=1, encoding='UTF-8', delimiter=',', header=True, extra_columns='REJECT')
    contract.update(changes)
    return validate_csv_content(data, contract, ['類別', '金額'])


def codes(result):
    return {issue['code'] for issue in result['issues']}


def test_exact_bytes_and_contract_evidence_without_data_exposure():
    content = '類別,金額\r\n機密樣本,120.50\r\n'.encode()
    result = check(content)
    assert result['status'] == 'CSV_STRUCTURE_VALIDATED_NOT_EXECUTABLE'
    assert result['content_checksum'] == sha256(content).hexdigest()
    assert result['complete'] and result['records_checked'] == 1
    assert result['execution_authorized'] is False
    assert '機密樣本' not in str(result) and '類別' not in str(result)
    assert result == check(content)


@pytest.mark.parametrize('data,code', [
    ('類別,金額,多餘\nA,1,2\n', 'CSV_EXTRA_COLUMNS'),
    ('金額,類別\n1,A\n', 'CSV_HEADER_MISMATCH'),
    ('類別,類別\nA,1\n', 'CSV_HEADER_DUPLICATE'),
    ('類別,金額\nA\n', 'CSV_MISSING_COLUMNS'),
    ('類別,金額\n"A,1\n', 'CSV_PARSE_ERROR'),
    ('類別,金額\n', 'CSV_DATA_EMPTY'),
    ('', 'CSV_HEADER_MISSING'),
    ('類別,金額\nA,\x00\n', 'CSV_NUL_CHARACTER'),
])
def test_malformed_content_blocked(data, code):
    result = check(data.encode())
    assert result['status'] == 'INVALID' and code in codes(result)


def test_ignore_allows_only_trailing_extra_columns_not_missing_or_reordered():
    result = check('類別,金額,其他\nA,1,x\nB,2\n'.encode(), extra_columns='IGNORE')
    assert not result['issues'] and result['records_with_extra_columns'] == 1
    assert 'CSV_MISSING_COLUMNS' in codes(check('類別,金額\nA\n'.encode(), extra_columns='IGNORE'))
    assert 'CSV_HEADER_MISMATCH' in codes(check('其他,類別,金額\nx,A,1\n'.encode(), extra_columns='IGNORE'))


def test_quote_newline_delimiter_and_no_header():
    result = check('"A;B\nC";"1"\n'.encode(), header=False, delimiter=';')
    assert not result['issues'] and result['records_checked'] == 1


def test_big5_and_utf8_bom_are_explicit():
    data = '類別,金額\nA,1\n'
    assert not check(data.encode('big5'), encoding='BIG5')['issues']
    assert 'CSV_ENCODING_INVALID' in codes(check(data.encode('big5')))
    assert 'CSV_BOM_CONTRACT_MISMATCH' in codes(check(data.encode('utf-8-sig')))
    assert not check(data.encode('utf-8-sig'), encoding='UTF-8-SIG')['issues']


def test_issue_and_resource_limits_never_pass_partial_scan(monkeypatch):
    import app.csv_content_validation as module
    result = check(('類別,金額\n' + 'A\n' * 25).encode())
    assert len(result['issues']) == 20 and not result['complete']
    monkeypatch.setattr(module, 'MAX_RECORDS', 1)
    assert 'CSV_RECORD_LIMIT' in codes(check('類別,金額\nA,1\nB,2\n'.encode()))
    monkeypatch.setattr(module, 'MAX_BYTES', 2)
    assert 'CSV_SIZE_LIMIT' in codes(check(b'123'))


def test_bad_contract_and_nonbytes_rejected_without_sensitive_values():
    assert 'CSV_CONTRACT_INVALID' in codes(check(b'a', encoding='unknown-secret'))
    assert 'CSV_BYTES_REQUIRED' in codes(check('not bytes'))
