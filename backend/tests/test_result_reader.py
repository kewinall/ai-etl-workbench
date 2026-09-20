from decimal import Decimal
import pytest
from app.expected_result import ResultColumn
from app import result_reader


class Cursor:
    description=[('value',)]
    def __init__(self,rows):self.rows=list(rows);self.calls=0
    def fetchmany(self,size):
        assert size==100;self.calls+=1
        batch=self.rows[:size];self.rows=self.rows[size:];return batch


def test_all_pages_and_exact_decimal():
    cursor=Cursor([(Decimal('12345678901234567890.123456789012345678'),)]*101)
    rows=result_reader.read_result_rows(cursor,[ResultColumn('value','DECIMAL')])
    assert len(rows)==101 and cursor.calls==3
    assert rows[0]['value']==Decimal('12345678901234567890.123456789012345678')


@pytest.mark.parametrize('description',[None,[('different',)],[('value',),('value',)]])
def test_metadata_mismatch_before_fetch(description):
    cursor=Cursor([]);cursor.description=description
    with pytest.raises(ValueError,match='COLUMN_ORDER'):result_reader.read_result_rows(cursor,[ResultColumn('value','TEXT')])
    assert cursor.calls==0


def test_partial_failure_is_not_partial_success():
    cursor=Cursor([(1,)])
    def fail(size):raise RuntimeError('private hostname and query')
    cursor.fetchmany=fail
    with pytest.raises(ValueError,match='^RESULT_READ_INCOMPLETE$'):
        result_reader.read_result_rows(cursor,[ResultColumn('value','INTEGER')])


@pytest.mark.parametrize('rows,code',[([(1,2)],'WIDTH'),([(1.5,)],'TYPE'),([(None,)],'NULL'),([(1,)]*10001,'ROW_LIMIT')])
def test_invalid_or_excessive_data_rejected(rows,code):
    with pytest.raises(ValueError,match=code):result_reader.read_result_rows(Cursor(rows),[ResultColumn('value','INTEGER')])


def test_content_budget_applies_across_pages(monkeypatch):
    monkeypatch.setattr(result_reader,'MAX_CANONICAL_BYTES',100)
    with pytest.raises(ValueError,match='CONTENT_LIMIT'):
        result_reader.read_result_rows(Cursor([('中文',)]*100),[ResultColumn('value','TEXT')])
