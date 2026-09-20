from dataclasses import replace
from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile
import pytest
from app.delivery_compiler import compile_delivery_components, build_checked_bundle_candidate
from app.release_bundle import BundleArtifact, MEMBERS
from test_etl_specification import design
from test_sdm_xlsx_structure import fixture as structural_sdm_fixture
from test_sdm_xlsx_semantics import workbook_fixture


def fixture():
    spec, run, naming = design()
    compiled = compile_delivery_components(spec, run, naming)
    items = []
    for kind in MEMBERS:
        # The SDM fixture does not assert valid XLSX or portability.
        content = compiled.get(kind.lower(), 'UNVERIFIED_TEST_CONTENT').encode()
        if kind == 'SDM': content = workbook_fixture(spec,run,naming)
        items.append(BundleArtifact(kind, content, sha256(content).hexdigest(), spec['run_id'], compiled['specification_checksum'], spec['naming']['checksum']))
    return spec, run, naming, compiled, items


def test_ddl_only_output_columns_in_spec_order_and_same_bundle_bytes():
    spec, run, naming, compiled, items = fixture()
    assert compiled['ddl'] == 'CREATE TABLE "ai_sample"."totals" (\n  "category" VARCHAR(32),\n  "total_amount" NUMERIC(18,2),\n  "row_count" BIGINT\n);\n'
    assert '"amount"' not in compiled['ddl']
    assert 'DROP' not in compiled['ddl'] and 'IF NOT EXISTS' not in compiled['ddl']
    assert compiled == compile_delivery_components(spec, run, naming)
    result = build_checked_bundle_candidate(items, spec, run, naming)
    with ZipFile(BytesIO(result['content'])) as archive:
        for kind in ('HPL', 'HWF', 'DDL', 'PARAMETERS'):
            assert archive.read(MEMBERS[kind]) == compiled[kind.lower()].encode()
    assert result['manifest']['portability'] == 'NOT_VERIFIED'
    assert result['release_ready'] is False


@pytest.mark.parametrize('kind', ['HPL', 'HWF', 'DDL', 'PARAMETERS'])
def test_changed_content_even_with_recomputed_digest_and_matching_labels_rejected(kind):
    spec, run, naming, compiled, items = fixture()
    i = next(i for i, item in enumerate(items) if item.kind == kind)
    content = items[i].content + b'\nchanged'
    items[i] = replace(items[i], content=content, checksum=sha256(content).hexdigest())
    with pytest.raises(ValueError, match='BUNDLE_COMPILER_CONTENT_MISMATCH'):
        build_checked_bundle_candidate(items, spec, run, naming)


def test_invalid_or_stale_spec_cannot_produce_ddl():
    spec, run, naming = design(); run['matches_current'] = False
    assert 'ddl' not in compile_delivery_components(spec, run, naming)
    with pytest.raises(ValueError, match='DELIVERY_VALID_SPECIFICATION_REQUIRED'):
        build_checked_bundle_candidate([], spec, run, naming)


def test_parameter_template_matches_declared_parameters_without_runtime_values():
    from xml.etree.ElementTree import fromstring
    spec, run, naming, compiled, items = fixture()
    assignments = [line.split('=', 1) for line in compiled['parameters'].splitlines() if line and not line.startswith('#')]
    assert assignments == [['SOURCE_CSV', '']]
    assert [p.findtext('name') for p in fromstring(compiled['hpl']).findall('info/parameters/parameter')] == ['SOURCE_CSV']
    assert [p.findtext('name') for p in fromstring(compiled['hwf']).findall('parameters/parameter')] == ['SOURCE_CSV']
    assert compiled['parameters_checksum'] == sha256(compiled['parameters'].encode()).hexdigest()
    assert 'etl_target' in compiled['parameters']
    assert 'does not load it automatically' in compiled['parameters']


def test_connection_material_in_parameter_file_is_rejected_even_with_correct_digest():
    spec, run, naming, compiled, items = fixture()
    i = next(i for i, item in enumerate(items) if item.kind == 'PARAMETERS')
    content = b'SOURCE_CSV=private-path\nPASSWORD=synthetic-private-value\n'
    items[i] = replace(items[i], content=content, checksum=sha256(content).hexdigest())
    with pytest.raises(ValueError, match='BUNDLE_COMPILER_CONTENT_MISMATCH'):
        build_checked_bundle_candidate(items, spec, run, naming)


def test_sdm_active_content_cannot_be_packaged():
    spec, run, naming, compiled, items = fixture()
    i = next(i for i, item in enumerate(items) if item.kind == 'SDM')
    content = structural_sdm_fixture({'xl/worksheets/sheet1.xml':b'<root><f>1+1</f></root>'})
    items[i] = replace(items[i], content=content, checksum=sha256(content).hexdigest())
    with pytest.raises(ValueError, match='SDM_XLSX_ACTIVE_CONTENT'):
        build_checked_bundle_candidate(items, spec, run, naming)
