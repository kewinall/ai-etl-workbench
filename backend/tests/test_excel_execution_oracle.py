from copy import deepcopy
import pytest
from app.execution_oracle import validate_execution_sources
from app.source_binding import execution_sources
from test_excel_specification import excel_design


@pytest.mark.parametrize('change',[None,'downgrade','missing_format','wrong_format','source_hash','multi','contract','unknown'])
def test_post_execution_excel_binding_cannot_be_downgraded(change):
    _,run,_=excel_design();config=deepcopy(run['input_snapshot']['source_config'])
    binding={'policy_version':'hop-single-attempt-v4',**execution_sources(config,4)}
    if change=='downgrade':binding['policy_version']='hop-single-attempt-v2';binding.pop('source_format')
    elif change=='missing_format':binding.pop('source_format')
    elif change=='wrong_format':binding['source_format']='CSV'
    elif change=='source_hash':binding['source_checksum']='0'*64
    elif change=='multi':binding['source_checksums']={'source.0':binding['source_checksum']}
    elif change=='contract':config.pop('excel_input_contract_v1')
    elif change=='unknown':binding['policy_version']='hop-single-attempt-v5'
    if change is None:validate_execution_sources(binding,config)
    else:
        with pytest.raises(ValueError):validate_execution_sources(binding,config)
