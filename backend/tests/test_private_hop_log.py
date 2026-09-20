import base64
import os
from uuid import uuid4
import pytest
from app.private_hop_log import encrypt_hop_log,decrypt_hop_log

@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv('PLATFORM_SETTINGS_ENCRYPTION_KEY',base64.urlsafe_b64encode(os.urandom(32)).decode())

def test_binary_roundtrip_is_encrypted_and_randomized():
    run=uuid4();content=b'private-host password=synthetic\xff'
    first=encrypt_hop_log(run,content);second=encrypt_hop_log(run,content)
    assert first['cipher_text']!=second['cipher_text']
    assert b'private-host' not in first['cipher_text']
    assert decrypt_hop_log(run,first)==content

@pytest.mark.parametrize('change',['run','cipher','checksum','size'])
def test_tampering_and_cross_run_substitution_rejected(change):
    run=uuid4();record=encrypt_hop_log(run,b'synthetic')
    if change=='run':run=uuid4()
    elif change=='cipher':record['cipher_text']=b'x'+record['cipher_text'][1:]
    elif change=='checksum':record['checksum']='0'*64
    else:record['size']+=1
    with pytest.raises(ValueError,match='PRIVATE_LOG_UNAVAILABLE_OR_CHANGED'):
        decrypt_hop_log(run,record)

def test_missing_key_never_falls_back_to_plaintext(monkeypatch):
    monkeypatch.delenv('PLATFORM_SETTINGS_ENCRYPTION_KEY')
    with pytest.raises(ValueError):encrypt_hop_log(uuid4(),b'synthetic')
