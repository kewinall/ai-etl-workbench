"""Explicit XLSX read policy; standalone until the versioned Run path supports it."""
from io import BytesIO
from typing import Literal
from openpyxl import load_workbook
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator


class ExcelInputContractV1(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    version: Literal[1]
    engine: Literal['POI']
    worksheet: str = Field(min_length=1, max_length=31)
    header_row: StrictInt = Field(ge=1, le=1000)
    blank_rows: Literal['SKIP', 'PRESERVE']
    missing_cells: Literal['NULL']
    extra_columns: Literal['REJECT']
    formulas: Literal['REJECT']
    trim_strings: Literal['NONE']
    on_error: Literal['FAIL']

    @field_validator('version', mode='before')
    @classmethod
    def exact_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError('EXCEL_CONTRACT_VERSION_INVALID')
        return value


def validate_excel_content(content, contract, field_names, *, max_rows=100000):
    """Full selected-sheet structural check, not data conversion or execution QA.

    Inspect formulas without cached-value substitution. Unselected sheets are
    outside this contract. Scan limits never produce a successful complete proof.
    """
    policy = ExcelInputContractV1.model_validate(contract)
    if (not field_names or len(field_names) > 512 or any(not isinstance(name, str) or not name for name in field_names)
            or len(set(field_names)) != len(field_names)):
        raise ValueError('EXCEL_FIELDS_INVALID')
    if type(max_rows) is not int or max_rows < 1:
        raise ValueError('EXCEL_SCAN_LIMIT_INVALID')
    book = load_workbook(BytesIO(content), read_only=True, data_only=False)
    try:
        if policy.worksheet not in book.sheetnames:
            raise ValueError('EXCEL_SHEET_MISSING')
        sheet = book[policy.worksheet]
        if (sheet.max_column or 0) > 512:
            raise ValueError('EXCEL_COLUMN_LIMIT')
        records = blanks = scanned = 0
        header_found = False
        for index, cells in enumerate(sheet.iter_rows(min_row=policy.header_row)):
            values = [cell.value for cell in cells]
            if len(values) > 512:
                raise ValueError('EXCEL_COLUMN_LIMIT')
            if any(cell.data_type == 'f' for cell in cells):
                raise ValueError('EXCEL_FORMULA_REJECTED')
            if any(cell.data_type == 'e' for cell in cells):
                raise ValueError('EXCEL_CELL_ERROR_REJECTED')
            if index == 0:
                names = [str(value).strip() if value is not None else '' for value in values]
                if names != field_names:
                    raise ValueError('EXCEL_HEADER_MISMATCH')
                header_found = True
                continue
            scanned += 1
            if scanned > max_rows:
                raise ValueError('EXCEL_SCAN_LIMIT_EXCEEDED')
            if any(value is not None for value in values[len(field_names):]):
                raise ValueError('EXCEL_EXTRA_COLUMNS_REJECTED')
            if all(value is None for value in values):
                blanks += 1
                if policy.blank_rows == 'SKIP':
                    continue
            records += 1
        if not header_found:
            raise ValueError('EXCEL_HEADER_MISSING')
        return {'status': 'EXCEL_STRUCTURE_VALIDATED_NOT_EXECUTABLE', 'complete': True,
                'rows_scanned': scanned, 'records_expected': records, 'blank_rows': blanks,
                'type_conversion_verified': False, 'execution_authorized': False}
    finally:
        book.close()
