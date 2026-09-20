"""In-memory, reproducible packaging. Not a release approval or portability gate.

Only the controller may resolve approved artifact bytes. This module does not
read paths, query history, or trust an artifact's claimed approval status.
"""
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
import re
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


MEMBERS = {
    'HPL': 'hop/pipeline.hpl',
    'HWF': 'hop/workflow.hwf',
    'DDL': 'vertica-ddl.sql',
    'SDM': 'SDM.xlsx',
    'PARAMETERS': 'parameters.example',
}
MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_BUNDLE_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class BundleArtifact:
    kind: str
    content: bytes
    checksum: str
    run_id: str
    specification_checksum: str
    naming_checksum: str


def _digest(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError('BUNDLE_INVALID_CHECKSUM')
    return value


def _run(value):
    if not isinstance(value, str):
        raise ValueError('BUNDLE_INVALID_RUN')
    try:
        if str(UUID(value)) != value:
            raise ValueError()
    except ValueError:
        raise ValueError('BUNDLE_INVALID_RUN') from None
    return value


def build_bundle_candidate(artifacts, *, run_id, specification_checksum, naming_checksum):
    """Validate byte/version integrity and package fixed names, never filesystem paths.

    This intentionally returns no RELEASE_READY / QA success. An orchestrator
    must still verify provenance, portability, QA and human approval.
    """
    binding = (_run(run_id), _digest(specification_checksum), _digest(naming_checksum))
    if not isinstance(artifacts, (list, tuple)) or len(artifacts) != len(MEMBERS):
        raise ValueError('BUNDLE_REQUIRED_ARTIFACTS')
    by_kind = {}
    total = 0
    for item in artifacts:
        if not isinstance(item, BundleArtifact) or item.kind not in MEMBERS or item.kind in by_kind:
            raise ValueError('BUNDLE_REQUIRED_ARTIFACTS')
        if (item.run_id, item.specification_checksum, item.naming_checksum) != binding:
            raise ValueError('BUNDLE_ARTIFACT_VERSION_MISMATCH')
        if type(item.content) is not bytes or not 0 < len(item.content) <= MAX_MEMBER_BYTES:
            raise ValueError('BUNDLE_ARTIFACT_SIZE')
        total += len(item.content)
        if total > MAX_BUNDLE_BYTES:
            raise ValueError('BUNDLE_TOTAL_SIZE')
        if sha256(item.content).hexdigest() != _digest(item.checksum):
            raise ValueError('BUNDLE_ARTIFACT_CHANGED')
        by_kind[item.kind] = item
    manifest = {
        'version': 1, 'document_type': 'ReleaseBundleCandidateV1',
        'status': 'CANDIDATE_NOT_RELEASED',
        'run_id': run_id, 'specification_checksum': specification_checksum,
        'naming_checksum': naming_checksum,
        'portability': 'NOT_VERIFIED', 'qa_passed': False, 'release_ready': False,
        'artifacts': [
            {'name': name, 'type': kind, 'checksum': by_kind[kind].checksum,
             'size_bytes': len(by_kind[kind].content)}
            for kind, name in MEMBERS.items()
        ],
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    output = BytesIO()
    with ZipFile(output, 'w', compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for name, content in [*( (name, by_kind[kind].content) for kind, name in MEMBERS.items()),
                              ('release-manifest.json', manifest_bytes)]:
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content, compresslevel=6)
    content = output.getvalue()
    return {'status': 'CANDIDATE_NOT_RELEASED', 'content': content,
            'checksum': sha256(content).hexdigest(), 'manifest': manifest,
            'manifest_checksum': sha256(manifest_bytes).hexdigest(),
            'qa_passed': False, 'release_ready': False}
