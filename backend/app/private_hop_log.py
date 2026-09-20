"""Encrypted private log payload, never a release artifact or public response."""
import base64
from hashlib import sha256
import json
from uuid import UUID
from .platform_harness import encrypt_secret,decrypt_secret

MAX_LOG_BYTES=10*1024*1024


def encrypt_hop_log(run_id,content):
    run=str(UUID(str(run_id)))
    if not isinstance(content,bytes) or len(content)>MAX_LOG_BYTES:
        raise ValueError('INVALID_PRIVATE_LOG')
    checksum=sha256(content).hexdigest()
    envelope={'version':1,'purpose':'HOP_PRIVATE_LOG','run_id':run,'checksum':checksum,
              'content':base64.b64encode(content).decode('ascii')}
    cipher,nonce=encrypt_secret(json.dumps(envelope,sort_keys=True,separators=(',',':')))
    return {'cipher_text':cipher,'nonce':nonce,'checksum':checksum,'size':len(content)}


def decrypt_hop_log(run_id,record):
    try:
        if len(record['cipher_text'])>MAX_LOG_BYTES*2 or len(record['nonce'])!=12:
            raise ValueError()
        envelope=json.loads(decrypt_secret(record['cipher_text'],record['nonce']))
        if envelope['version']!=1 or envelope['purpose']!='HOP_PRIVATE_LOG' or envelope['run_id']!=str(UUID(str(run_id))):
            raise ValueError()
        content=base64.b64decode(envelope['content'],validate=True)
        if len(content)>MAX_LOG_BYTES or len(content)!=record['size'] or sha256(content).hexdigest()!=envelope['checksum'] or envelope['checksum']!=record['checksum']:
            raise ValueError()
        return content
    except Exception:
        raise ValueError('PRIVATE_LOG_UNAVAILABLE_OR_CHANGED') from None
