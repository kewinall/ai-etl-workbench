import pytest
from app.oracle_schema import oracle_columns


def test_columns_keep_compiler_order_and_kinds():
    compiled={'specification':{'output_columns':['amount','label','count','active']},
              'output_types':{'count':'BIGINT','label':'VARCHAR(100)','amount':'NUMERIC(18,2)','active':'BOOLEAN'}}
    assert oracle_columns(compiled)==[
        {'name':'amount','kind':'DECIMAL','nullable':False},
        {'name':'label','kind':'TEXT','nullable':False},
        {'name':'count','kind':'INTEGER','nullable':False},
        {'name':'active','kind':'BOOLEAN','nullable':False}]


@pytest.mark.parametrize('kind',['DATE','TIMESTAMP','FLOAT',None])
def test_unsupported_type_never_silently_becomes_text(kind):
    with pytest.raises(ValueError,match='ORACLE_OUTPUT_TYPE_UNSUPPORTED'):
        oracle_columns({'specification':{'output_columns':['value']},'output_types':{'value':kind}})


def test_editor_rejects_more_columns_than_document_supports():
    names=[f'c{i}' for i in range(129)]
    with pytest.raises(ValueError,match='ORACLE_OUTPUT_COLUMNS_LIMIT'):
        oracle_columns({'specification':{'output_columns':names},'output_types':{name:'BIGINT' for name in names}})
