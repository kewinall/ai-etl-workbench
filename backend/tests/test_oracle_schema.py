import pytest
from app.oracle_schema import validate_oracle_schema


@pytest.mark.parametrize('declared,kind',[('VARCHAR(32)','TEXT'),('BIGINT','INTEGER'),('NUMERIC(18,2)','DECIMAL'),('BOOLEAN','BOOLEAN')])
def test_compiler_types_match_exact_oracle_kind(declared,kind):
    compiled={'specification':{'output_columns':['value']},'output_types':{'value':declared}}
    validate_oracle_schema({'columns':[{'name':'value','kind':kind}]},compiled)
    with pytest.raises(ValueError,match='ORACLE_OUTPUT_TYPE_MISMATCH'):
        validate_oracle_schema({'columns':[{'name':'value','kind':'DECIMAL' if kind!='DECIMAL' else 'TEXT'}]},compiled)


@pytest.mark.parametrize('declared',['DATE','TIMESTAMP','FLOAT','NUMERIC(99,2)',None])
def test_not_yet_supported_types_cannot_silently_become_text(declared):
    with pytest.raises(ValueError,match='ORACLE_OUTPUT_TYPE_UNSUPPORTED'):
        validate_oracle_schema({'columns':[{'name':'value','kind':'TEXT'}]},
                              {'specification':{'output_columns':['value']},'output_types':{'value':declared}})


def test_order_and_names_must_match():
    with pytest.raises(ValueError,match='ORACLE_OUTPUT_COLUMNS_MISMATCH'):
        validate_oracle_schema({'columns':[{'name':'b','kind':'INTEGER'},{'name':'a','kind':'INTEGER'}]},
                              {'specification':{'output_columns':['a','b']},'output_types':{}})
