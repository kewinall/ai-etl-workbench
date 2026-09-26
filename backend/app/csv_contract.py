"""Explicit CSV input semantics, never a file path, sample or execution permission."""
from copy import deepcopy
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, StrictBool, Field, field_validator


class CsvInputContractV1(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: Literal[1] = 1
    encoding: Literal['UTF-8', 'UTF-8-SIG', 'BIG5']
    delimiter: Literal[',', ';', '\t', '|']
    header: StrictBool
    extra_columns: Literal['REJECT', 'IGNORE']


class CsvInputContractsV1(BaseModel):
    """Per-source semantics; versioned separately to preserve single-file hashes."""
    model_config = ConfigDict(extra='forbid')
    version: Literal[1]
    sources: dict[str, CsvInputContractV1] = Field(min_length=2, max_length=32)

    @field_validator('version', mode='before')
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError('INTEGER_VERSION_REQUIRED')
        return value

    @field_validator('sources')
    @classmethod
    def exact_refs(cls, value):
        if any(not re.fullmatch(r'source\.(?:0|[1-9][0-9]?)', ref) for ref in value):
            raise ValueError('CSV_SOURCE_REF_INVALID')
        return value


def editable_csv_sources(config):
    sources = config.get('sources') or []
    return (2 <= len(sources) <= 32 and all(source.get('type') == 'CSV'
            and type(source.get('has_actual_data')) is bool for source in sources))


def validated_csv_contracts(config):
    """Exact coverage, no missing-source fallback or source.0 reuse."""
    if not editable_csv_sources(config):
        raise ValueError('CSV_MULTI_SOURCE_NOT_SUPPORTED')
    if 'csv_input_contract_v1' in config:
        raise ValueError('CSV_CONTRACT_FORMS_CONFLICT')
    parsed = CsvInputContractsV1.model_validate(config.get('csv_input_contracts_v1'))
    if set(parsed.sources) != {f'source.{index}' for index in range(len(config['sources']))}:
        raise ValueError('CSV_CONTRACT_SOURCE_COVERAGE_MISMATCH')
    return parsed.model_dump()


def source_csv_contract(config, source_ref):
    if editable_csv_source(config) and source_ref == 'source.0':
        if 'csv_input_contracts_v1' in config:
            raise ValueError('CSV_CONTRACT_FORMS_CONFLICT')
        return CsvInputContractV1.model_validate(config.get('csv_input_contract_v1')).model_dump()
    contracts = validated_csv_contracts(config)
    if source_ref not in contracts['sources']:
        raise ValueError('CSV_SOURCE_REF_UNKNOWN')
    return contracts['sources'][source_ref]


def revise_csv_contracts(config, changes):
    result = deepcopy(config)
    if changes is None:
        return result
    # Explicit migration to per-source semantics, never leave both competing forms.
    result.pop('csv_input_contract_v1', None)
    result['csv_input_contracts_v1'] = CsvInputContractsV1.model_validate(changes).model_dump()
    validated_csv_contracts(result)
    return result


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
    result.pop('csv_input_contracts_v1', None)
    return result


def csv_contract_issues(snapshot):
    config = snapshot.get('source_config') or {}
    sources = config.get('sources') or []
    if (snapshot.get('source_type') != 'CSV' and not any(s.get('type') == 'CSV' for s in sources)
            and 'csv_input_contracts_v1' not in config):
        return []
    if len(sources) > 1 or 'csv_input_contracts_v1' in config:
        try:
            validated_csv_contracts(config)
        except ValueError:
            missing = editable_csv_sources(config) and 'csv_input_contracts_v1' not in config
            return [dict(issue_type='MISSING' if missing else 'UNSUPPORTED',
                field_path='source_config.csv_input_contracts_v1',
                message='請逐一確認每個 CSV 的編碼、分隔符號、標題列及額外欄位政策；來源必須完全對應，不可混用單來源契約',
                suggestion={'required': True})]
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


def csv_sources_evidence(config):
    """Ordered whitelist for API/SA, never paths, uploaded rows or private IDs."""
    if len(config.get('sources') or []) <= 1 and 'csv_input_contracts_v1' not in config:
        return None
    try:
        contracts = validated_csv_contracts(config)
    except ValueError:
        return {'contract_status': 'INVALID' if 'csv_input_contracts_v1' in config else 'MISSING'}
    return {'version': 1, 'contract_status': 'CONFIRMED_INPUT_ONLY', 'sources': [
        {'source_ref': f'source.{index}',
         'acquisition': 'UPLOADED_CSV' if source['has_actual_data'] else 'PLATFORM_GENERATED_CSV',
         'contract': contracts['sources'][f'source.{index}']}
        for index, source in enumerate(config['sources'])]}
