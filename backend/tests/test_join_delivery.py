from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import pytest
from app.delivery_compiler import compile_delivery_components, build_checked_bundle_candidate
from app.release_bundle import BundleArtifact, MEMBERS
from app.sdm_specification import build_sdm_candidate
from app.sdm_renderer import render_sdm_xlsx
from app.sdm_xlsx_semantics import expected_sdm_cells, validate_sdm_xlsx
from test_join_semantics import join_design


def test_join_delivery_parameters_and_lineage_are_consistent():
    spec,run,naming = join_design()
    before = deepcopy((spec,run,naming))
    compiled = compile_delivery_components(spec,run,naming)
    names = ['SOURCE_CSV_0','SOURCE_CSV_1']
    assert [p.findtext('name') for p in ET.fromstring(compiled['hwf']).findall('parameters/parameter')] == names
    assert [line.split('=') for line in compiled['parameters'].splitlines() if line and not line.startswith('#')] == [[n,''] for n in names]
    document = build_sdm_candidate(spec,run,naming)['document']
    assert document['version'] == 2 and document['source_refs'] == ['source.0','source.1']
    assert document['joins'] == spec['joins']
    assert [(m['source_columns'][0]['source_ref'],m['source_columns'][0]['original_name']) for m in document['mappings']] == [
        ('source.0','客戶編號'),('source.0','名稱'),('source.1','客戶編號'),('source.1','名稱')]
    cells = expected_sdm_cells(spec,run,naming)
    assert 'source.0.客戶編號' in cells[0].values() and 'source.1.客戶編號' in cells[0].values()
    for value in ('source.0 LEFT JOIN source.1','NEVER_MATCH','EXPAND','CASE_SENSITIVE_NO_TRIM'):
        assert value in cells[1].values()
    rendered = render_sdm_xlsx(spec,run,naming)
    assert validate_sdm_xlsx(rendered['content'],spec,run,naming)['semantic_equality'] == 'CANDIDATE_LAYOUT_MATCHED'
    artifacts=[]
    for kind in MEMBERS:
        content = rendered['content'] if kind == 'SDM' else compiled[kind.lower()].encode()
        artifacts.append(BundleArtifact(kind,content,sha256(content).hexdigest(),spec['run_id'],
                                        compiled['specification_checksum'],spec['naming']['checksum']))
    candidate = build_checked_bundle_candidate(artifacts,spec,run,naming)
    with ZipFile(BytesIO(candidate['content'])) as archive:
        assert set(archive.namelist()) == {*MEMBERS.values(),'release-manifest.json'}
        assert archive.read(MEMBERS['PARAMETERS']) == compiled['parameters'].encode()
    assert not candidate['release_ready'] and (spec,run,naming) == before
    broken = artifacts.copy()
    index = next(i for i,a in enumerate(broken) if a.kind == 'PARAMETERS')
    content = compiled['parameters'].replace('SOURCE_CSV_1=', 'SOURCE_CSV=').encode()
    broken[index] = replace(broken[index],content=content,checksum=sha256(content).hexdigest())
    with pytest.raises(ValueError,match='BUNDLE_COMPILER_CONTENT_MISMATCH'):
        build_checked_bundle_candidate(broken,spec,run,naming)


def test_changed_join_cannot_reuse_old_sdm_even_with_new_valid_specification():
    spec,run,naming = join_design()
    old = render_sdm_xlsx(spec,run,naming)['content']
    spec['joins'][0]['join_type'] = 'INNER'
    run['input_snapshot']['target_config']['join_contract_v1']['joins'][0]['join_type'] = 'INNER'
    with pytest.raises(ValueError,match='SDM_XLSX_SPECIFICATION_MISMATCH'):
        validate_sdm_xlsx(old,spec,run,naming)
