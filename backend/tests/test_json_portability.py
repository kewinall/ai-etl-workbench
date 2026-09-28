"""Synthetic proof contract checks, not native replay acceptance."""
from copy import deepcopy
import pytest
from app.release_portability import validate_portability
from app.sa_contract import digest
from test_formal_release_bundle import proof_fixture


def fixture():
    candidate,row=proof_fixture()
    reader=dict(version=1,reader_checksum='d'*64,original_byte_count=20,reader_byte_count=20,
                normalization='NONE',profile_checksum='a'*64,contract_checksum='b'*64)
    receipt=dict(version=1,scope='PRIVATE_LAUNCHER_SYSTEM_PROPERTY_RECEIPT',
                 HOP_JSON_INPUT_INCLUDE_NULLS='Y',qa_passed=False,log_checksum=row['evidence']['hop_log_checksum'])
    row['evidence'].update(version=5,source_format='JSON',json_reader=deepcopy(reader),json_runtime_receipt=receipt)
    row['checksum']=digest(row['evidence'])
    return candidate,row,reader


def check(candidate,row,reader,**changes):
    options=dict(expected_checksum='f'*64,expected_count=1,source_format='JSON',json_reader=reader)
    return validate_portability(row,candidate,'d'*64,**{**options,**changes})


def test_json_proof_requires_reader_and_explicit_format():
    candidate,row,reader=fixture()
    assert check(candidate,row,reader)['version']==5
    for changes in ({'source_format':None},{'source_format':'XLSX'},{'json_reader':None},
                    {'source_checksums':{'source.0':'d'*64}},{'source_order':{}}):
        with pytest.raises(ValueError):check(candidate,row,reader,**changes)
    old_candidate,old_row=proof_fixture()
    with pytest.raises(ValueError):check(old_candidate,old_row,reader)


@pytest.mark.parametrize('group,key,value',[
    ('json_reader','reader_checksum','0'*64),('json_reader','original_byte_count',True),
    ('json_reader','profile_checksum','0'*64),('json_reader','contract_checksum','0'*64),
    ('json_reader','normalization','RESERIALIZED'),('json_reader','version',True),
    ('json_runtime_receipt','version',True),('json_runtime_receipt','qa_passed',0),
    ('json_runtime_receipt','HOP_JSON_INPUT_INCLUDE_NULLS','N'),
    ('json_runtime_receipt','log_checksum','0'*64),('json_runtime_receipt','scope','SYNTHETIC')])
def test_json_proof_mutation_rejected_even_after_checksum_recomputed(group,key,value):
    candidate,row,reader=fixture()
    row['evidence'][group][key]=value;row['checksum']=digest(row['evidence'])
    with pytest.raises(ValueError):check(candidate,row,reader)
