"""Specification-owned HPL/HWF/DDL content; never executes SQL or grants release."""
from hashlib import sha256
from .hwf_compiler import compile_hwf
from .etl_specification import _type
from .release_bundle import build_bundle_candidate, BundleArtifact
from .sdm_xlsx_semantics import validate_sdm_xlsx


PARAMETERS_TEMPLATE = '''# AI ETL Workbench candidate parameters. Not an executable configuration.
# SOURCE_CSV must be supplied at execution time; source data is not included.
SOURCE_CSV=
# Configure local pipeline/workflow run configurations in the destination Hop environment.
# Configure the etl_target connection separately in destination Hop metadata.
# No credentials, connection addresses, or runtime data belong in this template.
# This file is documentation only; Hop does not load it automatically.
'''

PARAMETERS_TEMPLATE_V2 = PARAMETERS_TEMPLATE.replace(
    '# SOURCE_CSV must be supplied at execution time; source data is not included.\nSOURCE_CSV=\n',
    '# Both CSV sources must be supplied separately; source data is not included.\n'
    '# SOURCE_CSV_0 binds source.0 (left); SOURCE_CSV_1 binds source.1 (right).\n'
    'SOURCE_CSV_0=\nSOURCE_CSV_1=\n')


def compile_delivery_components(payload, run, naming):
    compiled = compile_hwf(payload, run, naming)
    if 'hwf' not in compiled:
        return compiled
    spec = compiled['specification']
    parameters = PARAMETERS_TEMPLATE_V2 if spec['version'] == 2 else PARAMETERS_TEMPLATE
    columns = []
    for name in spec['output_columns']:
        declared = _type(compiled['output_types'][name])
        if declared is None:
            raise ValueError('DELIVERY_UNSUPPORTED_TYPE')
        columns.append(f'  "{name}" {declared[1]}')
    ddl = (f'CREATE TABLE "{spec["target_schema"]}"."{spec["target_table"]}" (\n'
           + ',\n'.join(columns) + '\n);\n')
    return {**compiled, 'ddl': ddl, 'ddl_checksum': sha256(ddl.encode()).hexdigest(),
            'parameters': parameters,
            'parameters_checksum': sha256(parameters.encode()).hexdigest(),
            'compiler_status': 'DELIVERY_COMPONENTS_NOT_RELEASED',
            'qa_passed': False, 'release_ready': False}


def build_checked_bundle_candidate(artifacts, payload, run, naming):
    """Check compiler-owned bytes, not only caller-supplied checksum labels.

    SDM content and provenance still require their dedicated gates.
    This API must not be interpreted as full portability or approval checking.
    """
    compiled = compile_delivery_components(payload, run, naming)
    if 'ddl' not in compiled:
        raise ValueError('DELIVERY_VALID_SPECIFICATION_REQUIRED')
    if not isinstance(artifacts, (list, tuple)):
        raise ValueError('BUNDLE_REQUIRED_ARTIFACTS')
    for item in artifacts:
        if not isinstance(item, BundleArtifact):
            raise ValueError('BUNDLE_REQUIRED_ARTIFACTS')
        if item.kind in ('HPL', 'HWF', 'DDL', 'PARAMETERS') and item.content != compiled[item.kind.lower()].encode():
            raise ValueError('BUNDLE_COMPILER_CONTENT_MISMATCH')
        if item.kind == 'SDM':
            validate_sdm_xlsx(item.content,payload,run,naming)
    spec = compiled['specification']
    return build_bundle_candidate(artifacts, run_id=spec['run_id'],
        specification_checksum=compiled['specification_checksum'], naming_checksum=spec['naming']['checksum'])
