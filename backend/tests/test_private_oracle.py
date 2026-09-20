import base64
from hashlib import sha256
import json
from uuid import uuid4
import pytest
from app.private_oracle import encrypt_oracle,decrypt_oracle


def sealed(monkeypatch):
    monkeypatch.setenv('PLATFORM_SETTINGS_ENCRYPTION_KEY',base64.urlsafe_b64encode(b'x'*32).decode())
    content=json.dumps({'version':1,'specification_checksum':'a'*64,'naming_checksum':'b'*64,
        'columns':[{'name':'name','kind':'TEXT','nullable':False}], 'rows':[{'name':'private synthetic row'}]}).encode()
    run,spec=uuid4(),uuid4()
    record=encrypt_oracle(run,spec,content,document_checksum=sha256(content).hexdigest(),specification_checksum='a'*64,naming_checksum='b'*64)
    return run,spec,content,record


def test_encrypted_roundtrip_and_random_nonce(monkeypatch):
    run,spec,content,record=sealed(monkeypatch)
    assert decrypt_oracle(run,spec,record)==content
    assert b'private synthetic row' not in record['cipher_text']
    other=encrypt_oracle(run,spec,content,**{key:record[key] for key in ('document_checksum','specification_checksum','naming_checksum')})
    assert other['nonce']!=record['nonce']


@pytest.mark.parametrize('change',['run','spec','checksum','size','cipher','key'])
def test_binding_or_tamper_rejected_without_payload_disclosure(monkeypatch,change):
    run,spec,content,record=sealed(monkeypatch)
    if change=='run':run=uuid4()
    if change=='spec':spec=uuid4()
    if change=='checksum':record['document_checksum']='c'*64
    if change=='size':record['size']+=1
    if change=='cipher':record['cipher_text']=bytes([record['cipher_text'][0]^1])+record['cipher_text'][1:]
    if change=='key':monkeypatch.setenv('PLATFORM_SETTINGS_ENCRYPTION_KEY',base64.urlsafe_b64encode(b'y'*32).decode())
    with pytest.raises(ValueError,match='^ORACLE_UNAVAILABLE_OR_CHANGED$'):
        decrypt_oracle(run,spec,record)
