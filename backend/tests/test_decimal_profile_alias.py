from app.etl_specification import validate_specification
from test_etl_specification import design


def test_profile_decimal_alias_does_not_reject_exact_numeric_contract():
    spec,run,naming=design()
    run['input_snapshot']['source_config']['sources'][0]['fields'][1]['type']='DECIMAL(12,2)'
    result=validate_specification(spec,run,naming)
    assert result['status']=='VALIDATED_NOT_APPROVED',result


def test_profile_decimal_alias_keeps_precision_narrowing_guard():
    spec,run,naming=design()
    run['input_snapshot']['source_config']['sources'][0]['fields'][1]['type']='DECIMAL(18,4)'
    result=validate_specification(spec,run,naming)
    assert result['status']=='INVALID'
    assert any(i['code']=='SPEC_SOURCE_TYPE_NARROWING' for i in result['issues'])
