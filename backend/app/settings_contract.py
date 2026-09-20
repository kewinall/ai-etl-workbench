"""Write-time contracts shared by both settings API routes.

These contracts validate stored preferences; they do not imply runtime wiring.
"""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class SettingsValue(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Governance(SettingsValue):
    sample_schema: Literal['ai_sample'] = 'ai_sample'
    english_identifier: Literal['snake_case'] = 'snake_case'


class ReleasePolicy(SettingsValue):
    sample_rows: int = Field(default=10, ge=1, le=10)
    require_naming_contract: Literal[True] = True


class ValidationPolicy(SettingsValue):
    strategy: Literal['FIRST_10_VALID_ROWS'] = 'FIRST_10_VALID_ROWS'
    max_rows: int = Field(default=10, ge=1, le=10)
    post_write_count: Literal[True] = True


class VaultPolicy(SettingsValue):
    encryption: Literal['AES-256-GCM'] = 'AES-256-GCM'
    key_source: Literal['PLATFORM_SETTINGS_ENCRYPTION_KEY'] = 'PLATFORM_SETTINGS_ENCRYPTION_KEY'


CONTRACTS = {
    'data_governance_naming_rules': Governance,
    'validation_release_policy': ReleasePolicy,
    'validation_policy': ValidationPolicy,
    'security_secret_vault': VaultPolicy,
}


def validate_setting(key: str, value: dict) -> dict:
    contract = CONTRACTS.get(key)
    if contract is None:
        return value
    try:
        # Pydantic Literal[True] also accepts 1; require actual booleans.
        for field in ('require_naming_contract', 'post_write_count'):
            if field in value and value[field] is not True:
                raise ValueError(f'{field} 為必要驗證，不可停用')
        return contract.model_validate(value).model_dump()
    except ValidationError as exc:
        # Never include submitted values or validator context in API errors.
        fields = ', '.join('.'.join(map(str, e['loc'])) for e in exc.errors())
        raise ValueError(f'設定欄位不合法：{fields}；受控 schema、命名格式與安全政策不可變更，驗證筆數須為 1–10 的整數') from None
