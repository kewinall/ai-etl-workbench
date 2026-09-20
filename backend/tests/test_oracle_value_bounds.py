import pytest
from app.oracle_schema import validate_oracle_schema


def check(declared,kind,value):
    validate_oracle_schema({'columns':[{'name':'value','kind':kind}], 'rows':[{'value':value}]},
        {'specification':{'output_columns':['value']},'output_types':{'value':declared}})


@pytest.mark.parametrize('value',['999.99','-999.99','00001.2300','0.000','-0.000',None])
def test_decimal_exactly_representable(value):check('NUMERIC(5,2)','DECIMAL',value)


@pytest.mark.parametrize('value,code',[('1000','PRECISION'),('-1000.00','PRECISION'),('0.001','SCALE'),('999.999','SCALE')])
def test_decimal_never_rounds_or_overflows(value,code):
    with pytest.raises(ValueError,match=code):check('NUMERIC(5,2)','DECIMAL',value)


def test_fraction_only_and_zero_scale():
    check('NUMERIC(2,2)','DECIMAL','0.99')
    check('NUMERIC(2,0)','DECIMAL','99.000')
    with pytest.raises(ValueError,match='PRECISION'):check('NUMERIC(2,2)','DECIMAL','1')


def test_text_width_is_utf8_bytes_not_characters():
    check('VARCHAR(6)','TEXT','中文')
    with pytest.raises(ValueError,match='WIDTH'):check('VARCHAR(5)','TEXT','中文')
    check('VARCHAR(4)','TEXT','😀')
    with pytest.raises(ValueError,match='WIDTH'):check('VARCHAR(3)','TEXT','😀')


def test_integer_null_sentinel_is_not_an_answer_value():
    check('BIGINT','INTEGER',-(2**63)+1)
    check('BIGINT','INTEGER',2**63-1)
    with pytest.raises(ValueError,match='RANGE'):check('BIGINT','INTEGER',-(2**63))
