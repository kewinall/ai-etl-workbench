"""Path-free binding for the ordered, complete two-source execution input set."""
from hashlib import sha256
import json
import re


def source_set_checksum(checksums):
    if (not isinstance(checksums, dict) or set(checksums) != {'source.0', 'source.1'}
            or any(not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value)
                   for value in checksums.values())):
        raise ValueError('SOURCE_SET_BINDING_INVALID')
    return sha256(json.dumps(checksums, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def execution_sources(config, specification_version):
    """Canonical input binding; this does not grant execution permission."""
    sources = config.get('sources') or []
    if (type(specification_version) is not int or specification_version not in (1, 2)
            or len(sources) != specification_version
            or any(source.get('type') != 'CSV' or not source.get('upload_id') for source in sources)):
        raise ValueError('VERIFIED_UPLOADED_CSV_REQUIRED')
    checksums = {f'source.{i}': source.get('checksum') for i, source in enumerate(sources)}
    if any(not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value) for value in checksums.values()):
        raise ValueError('SOURCE_BINDING_REQUIRED')
    if specification_version == 1:
        return {'source_checksum': checksums['source.0']}
    return {'source_checksums': checksums, 'source_checksum': source_set_checksum(checksums)}


def expected_prepared_binding(authorization):
    """Retain every source in both reservation and final write checks."""
    expected = {key: authorization[key] for key in ('run_id', 'specification_id',
        'specification_checksum', 'input_checksum', 'settings_checksum', 'hpl_checksum', 'source_checksum')}
    expected['approval_id'] = authorization['specification_approval_id']
    if 'source_checksums' in authorization:
        checksums = authorization['source_checksums']
        if source_set_checksum(checksums) != authorization['source_checksum']:
            raise ValueError('SOURCE_SET_BINDING_INVALID')
        expected['source_checksums'] = dict(checksums)
    return expected
