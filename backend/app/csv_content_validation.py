"""Bounded content preflight, not ETL: no path access, row transformation or DB writes."""
import csv
import io
from hashlib import sha256

from .csv_contract import CsvInputContractV1
from .sa_contract import digest

MAX_BYTES = 50 * 1024 * 1024
MAX_RECORDS = 1_000_000
MAX_ISSUES = 20


def validate_csv_content(content: bytes, contract, source_columns: list[str]):
    """Validate exact input bytes; return metadata only, never cell/header values.

    Header matching is positional and exact. IGNORE permits trailing columns only;
    it never permits missing/reordered required columns. No bytes are rewritten.
    Quoting follows Python csv's strict Excel dialect (double quote enclosure).
    A successful preflight is not proof of Hop parser equivalence or type validity.
    """
    result = {'status': 'INVALID', 'execution_authorized': False, 'issues': [],
              'records_checked': 0, 'records_with_extra_columns': 0, 'complete': False}

    def issue(code, record=None):
        if len(result['issues']) < MAX_ISSUES:
            result['issues'].append({'code': code, 'record': record})

    if not isinstance(content, bytes):
        issue('CSV_BYTES_REQUIRED')
        return result
    if len(content) > MAX_BYTES:
        issue('CSV_SIZE_LIMIT')
        return result
    result['content_checksum'] = sha256(content).hexdigest()
    result['byte_count'] = len(content)
    try:
        parsed = CsvInputContractV1.model_validate(contract)
    except ValueError:
        issue('CSV_CONTRACT_INVALID')
        return result
    if (not isinstance(source_columns, list) or not source_columns or len(source_columns) > 200
            or any(not isinstance(name, str) or not name or '\x00' in name for name in source_columns)
            or len(set(source_columns)) != len(source_columns)):
        issue('CSV_SOURCE_COLUMNS_INVALID')
        return result
    result['contract_checksum'] = digest(parsed.model_dump())
    result['source_columns_checksum'] = digest(source_columns)
    if parsed.encoding == 'UTF-8' and content.startswith(b'\xef\xbb\xbf'):
        issue('CSV_BOM_CONTRACT_MISMATCH')
        return result
    try:
        text = content.decode({'UTF-8': 'utf-8', 'UTF-8-SIG': 'utf-8-sig', 'BIG5': 'big5'}[parsed.encoding], errors='strict')
    except UnicodeError:
        issue('CSV_ENCODING_INVALID')
        return result
    if '\x00' in text:
        issue('CSV_NUL_CHARACTER')
        return result
    reader = csv.reader(io.StringIO(text, newline=''), delimiter=parsed.delimiter,
                        quotechar='"', doublequote=True, strict=True)
    width = len(source_columns)
    try:
        if parsed.header:
            header = next(reader, None)
            if header is None:
                issue('CSV_HEADER_MISSING', 0)
                result['complete'] = True
                return result
            if len(header) != len(set(header)):
                issue('CSV_HEADER_DUPLICATE', 0)
            if header[:width] != source_columns:
                issue('CSV_HEADER_MISMATCH', 0)
            if len(header) > width and parsed.extra_columns == 'REJECT':
                issue('CSV_EXTRA_COLUMNS', 0)
        for record, row in enumerate(reader, 1):
            if record > MAX_RECORDS:
                issue('CSV_RECORD_LIMIT', record)
                return result
            result['records_checked'] = record
            if len(row) < width:
                issue('CSV_MISSING_COLUMNS', record)
            elif len(row) > width:
                result['records_with_extra_columns'] += 1
                if parsed.extra_columns == 'REJECT':
                    issue('CSV_EXTRA_COLUMNS', record)
            if len(result['issues']) >= MAX_ISSUES:
                # Deliberately incomplete: never certify a partially scanned file.
                return result
    except csv.Error:
        issue('CSV_PARSE_ERROR', result['records_checked'] + 1)
        return result
    result['complete'] = True
    if result['records_checked'] == 0:
        issue('CSV_DATA_EMPTY')
    if not result['issues']:
        result['status'] = 'CSV_STRUCTURE_VALIDATED_NOT_EXECUTABLE'
    return result
