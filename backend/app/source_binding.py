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
