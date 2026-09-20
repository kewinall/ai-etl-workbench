"""Validate the existing confirmation payload before any DB write."""
from pydantic import BaseModel, ConfigDict, Field


class NamingColumnInput(BaseModel):
    model_config = ConfigDict(extra='allow')
    source_name: str = Field(min_length=1, max_length=256)
    english_name: str = Field(pattern=r'^[a-z_][a-z0-9_]{0,62}$')
    vertica_type: str = Field(min_length=1, max_length=100)
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    reason: str = Field(min_length=1, max_length=2000)


class NamingContractInput(BaseModel):
    columns: list[NamingColumnInput] = Field(min_length=1, max_length=200)
