import pytest
from pydantic import ValidationError
from app.naming_input import NamingContractInput


def test_required_metadata_missing_is_validation_error_not_database_keyerror():
    with pytest.raises(ValidationError):
        NamingContractInput.model_validate({'columns':[{'source_name':'類別','english_name':'category','vertica_type':'VARCHAR(32)'}]})


@pytest.mark.parametrize('value', [-1, 2, float('nan'), float('inf')])
def test_confidence_is_bounded_and_finite(value):
    with pytest.raises(ValidationError):
        NamingContractInput.model_validate({'columns':[{'source_name':'類別','english_name':'category','vertica_type':'VARCHAR(32)','confidence':value,'reason':'manual'}]})


def test_legacy_suggestion_and_metric_columns_are_supported():
    value = NamingContractInput.model_validate({'columns':[{'source_name':'$metric.total','english_name':'total_amount','vertica_type':'NUMERIC(18,2)','confidence':1,'reason':'manual'}]})
    assert value.columns[0].model_dump()['confidence'] == 1
