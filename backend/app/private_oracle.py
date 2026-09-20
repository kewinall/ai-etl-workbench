"""Private expected-result payload for future control-store persistence.

Not an API or approval mechanism. The caller supplies trusted Run/specification
bindings and pinned document checksum; no secret key is persisted in this record.
"""
import base64
from hashlib import sha256
import json
from uuid import UUID
from .platform_harness import encrypt_secret, decrypt_secret
from .result_oracle import compare_oracle_document


def encrypt_oracle(run_id,specification_id,content,*,document_checksum,specification_checksum,naming_checksum):
    binding={'run_id':str(UUID(str(run_id))),'specification_id':str(UUID(str(specification_id))),
             'document_checksum':document_checksum,'specification_checksum':specification_checksum,'naming_checksum':naming_checksum}
    # Validate the entire oracle before sealing; this comparison grants nothing.
    compare_oracle_document(content,[],document_checksum=document_checksum,
                            specification_checksum=specification_checksum,naming_checksum=naming_checksum)
    envelope={'version':1,'purpose':'EXPECTED_RESULT_ORACLE',**binding,
              'content':base64.b64encode(content).decode('ascii')}
    cipher,nonce=encrypt_secret(json.dumps(envelope,sort_keys=True,separators=(',',':')))
    return {**binding,'cipher_text':cipher,'nonce':nonce,'size':len(content)}


def decrypt_oracle(run_id,specification_id,record):
    try:
        if len(record['cipher_text'])>16*1024*1024 or len(record['nonce'])!=12:
            raise ValueError()
        envelope=json.loads(decrypt_secret(record['cipher_text'],record['nonce']))
        binding={'run_id':str(UUID(str(run_id))),'specification_id':str(UUID(str(specification_id))),
                 **{key:record[key] for key in ('document_checksum','specification_checksum','naming_checksum')}}
        if envelope['version']!=1 or envelope['purpose']!='EXPECTED_RESULT_ORACLE' or any(envelope.get(key)!=value for key,value in binding.items()):
            raise ValueError()
        content=base64.b64decode(envelope['content'],validate=True)
        if len(content)>8*1024*1024 or len(content)!=record['size'] or sha256(content).hexdigest()!=record['document_checksum']:
            raise ValueError()
        return content
    except Exception:
        raise ValueError('ORACLE_UNAVAILABLE_OR_CHANGED') from None
