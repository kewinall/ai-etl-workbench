from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator


class EffortRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_key: str = Field(min_length=8, max_length=160)
    action: Literal['START','STOP','ABANDON']
    actor: Literal['HUMAN_SELF_REPORTED','DELEGATED_AGENT','FUNCTIONAL_TEST']
    mode: Literal['WORKBENCH','MANUAL_BASELINE']
    session_id: UUID | None = None
    expected_protocol_checksum: str = Field(pattern=r'^[a-f0-9]{64}$')
    confirmed: StrictBool
    human_attested: StrictBool = False

    @model_validator(mode='after')
    def explicit_declaration(self):
        if not self.confirmed or self.human_attested != (self.actor=='HUMAN_SELF_REPORTED'):
            raise ValueError('必須明確確認操作者來源；真人為自行聲明，不代表已驗證身分')
        if (self.action=='START') != (self.session_id is None):
            raise ValueError('開始不可指定 session；結束或放棄必須綁定 session')
        return self
