from copy import deepcopy
from pathlib import Path
from hashlib import sha256
import pytest
from app.json_replay_source import verify_staged_json
from app.json_execution_binding import reader_binding
from app.json_input_contract import prepare_json_reader_content
from test_json_specification import json_design,CONTENT


@pytest.mark.parametrize('bom',[False,True])
@pytest.mark.parametrize('changed',['none','original','reader','evidence','missing'])
def test_json_replay_checks_both_files_and_evidence(tmp_path,bom,changed):
    content=(b'\xef\xbb\xbf' if bom else b'')+CONTENT
    spec,run,_=json_design(content)
    config=run['input_snapshot']['source_config']
    source=config['sources'][0]
    data,evidence=prepare_json_reader_content(content,config['json_input_contract_v1'],
        [f['name'] for f in source['fields']],column_types=[f['type'] for f in source['fields']])
    staged=dict(path=tmp_path/'source.json',original_path=tmp_path/'source-original.json',evidence=deepcopy(evidence))
    staged['path'].write_bytes(data);staged['original_path'].write_bytes(content)
    binding=reader_binding(evidence,spec['json_source'])
    if changed=='original':staged['original_path'].write_bytes(b' '+content[1:])
    if changed=='reader':staged['path'].write_bytes(b' '+data[1:])
    if changed=='evidence':staged['evidence']['reader_content_checksum']='0'*64
    if changed=='missing':staged['path']=tmp_path/'missing.json'
    if changed=='none':verify_staged_json(staged,binding,spec['json_source'])
    else:
        with pytest.raises(ValueError):verify_staged_json(staged,binding,spec['json_source'])
