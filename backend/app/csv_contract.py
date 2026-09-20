"""Explicit CSV input semantics, never a file path, sample or execution permission."""
from copy import deepcopy
from typing import Literal
from pydantic import BaseModel, ConfigDict, StrictBool


class CsvInputContractV1(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: Literal[1] = 1
    encoding: Literal['UTF-8', 'UTF-8-SIG', 'BIG5']
    delimiter: Literal[',', ';', '\t', '|']
    header: StrictBool
    extra_columns: Literal['REJECT', 'IGNORE']


def editable_csv_source(config):
    sources = config.get('sources') or []
    return (len(sources) == 1 and sources[0].get('type') == 'CSV'
            and type(sources[0].get('has_actual_data')) is bool)


def revise_csv_contract(config, changes):
    result = deepcopy(config)
    if changes is None:
        return result
    if not editable_csv_source(config):
        raise ValueError('CSV_CONTRACT_EDIT_NOT_SUPPORTED')
    result['csv_input_contract_v1'] = CsvInputContractV1.model_validate(changes).model_dump()
    return result


def csv_contract_issues(snapshot):
    config = snapshot.get('source_config') or {}
    sources = config.get('sources') or []
    if snapshot.get('source_type') != 'CSV' and not any(s.get('type') == 'CSV' for s in sources):
        return []
    def issue(kind, message):
        return [dict(issue_type=kind, field_path='source_config.csv_input_contract_v1', message=message, suggestion={'required': True})]
    if not editable_csv_source(config):
        return issue('UNSUPPORTED', 'CSV 輸入契約目前需單一且已指定資料取得方式的 CSV 來源；不可推測多來源或舊式路徑設定')
    if 'csv_input_contract_v1' not in config:
        return issue('MISSING', '請確認 CSV 編碼、分隔符號、標題列及額外欄位政策；平台不會自行採用預設值')
    try:
        CsvInputContractV1.model_validate(config['csv_input_contract_v1'])
    except ValueError:
        return issue('UNSUPPORTED', 'CSV 輸入契約格式不合法，請重新補正')
    return []


def csv_evidence(config):
    """Expose semantic contract only; source.0 is an opaque snapshot binding, not a physical path."""
    if not editable_csv_source(config):
        return None
    value = {'source_ref': 'source.0', 'acquisition': 'UPLOADED_CSV' if config['sources'][0]['has_actual_data'] else 'PLATFORM_GENERATED_CSV'}
    raw = config.get('csv_input_contract_v1')
    if raw is None:
        return {**value, 'contract_status': 'MISSING'}
    try:
        return {**value, 'contract_status': 'CONFIRMED_INPUT_ONLY', **CsvInputContractV1.model_validate(raw).model_dump()}
    except ValueError:
        return {**value, 'contract_status': 'INVALID'}
