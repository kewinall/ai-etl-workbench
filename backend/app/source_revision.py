"""Bounded metadata editing for a single synthetic source, not file rewriting."""
from copy import deepcopy
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceFieldV1(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    type: Literal['BIGINT', 'INTEGER', 'NUMERIC', 'FLOAT', 'VARCHAR', 'BOOLEAN', 'DATE', 'TIMESTAMP']


class SourceFieldsV1(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fields: list[SourceFieldV1] = Field(min_length=1, max_length=200)

    @model_validator(mode='after')
    def unique_names(self):
        names = [field.name.casefold() for field in self.fields]
        if len(set(names)) != len(names):
            raise ValueError('DUPLICATE_SOURCE_FIELDS')
        return self


def editable_source(config):
    sources = config.get('sources') or []
    return (len(sources) == 1 and sources[0].get('has_actual_data') is False
            and not (set(config) - {'sources', 'requirement_supplement', 'csv_input_contract_v1'})
            and not (set(sources[0]) - {'type', 'alias', 'has_actual_data', 'fields'})
            and all(not (set(field) - {'name', 'type', 'nullable', 'length', 'precision', 'scale', 'description'}) for field in sources[0].get('fields', [])))


def revise_source(config, changes):
    if changes is None:
        return deepcopy(config)
    if not editable_source(config):
        raise ValueError('SOURCE_METADATA_EDIT_NOT_SUPPORTED')
    contract = SourceFieldsV1.model_validate(changes)
    result = deepcopy(config)
    previous = {field.get('name'): field for field in result['sources'][0].get('fields', [])}
    result['sources'][0]['fields'] = [{**previous.get(field.name, {}), **field.model_dump()} for field in contract.fields]
    return result
