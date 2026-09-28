import json
from hashlib import sha256
import pytest
import oracle_fixture
from app.result_oracle import compare_oracle_document


@pytest.mark.parametrize('version',[1,2])
def test_fixture_preserves_ordered_oracle_contract(monkeypatch,version):
    context=dict(version=version,specification_checksum='a'*64,naming_checksum='b'*64,
                 columns=[dict(name='source_position',kind='INTEGER',nullable=False)])
    if version==2:
        context.update(comparison='EXACT_SOURCE_SEQUENCE',ordinal_column='source_position')
    monkeypatch.setattr(oracle_fixture,'oracle_editor_context',lambda *args:context)
    saved=[]
    def save(*args):
        content=args[-1]
        compare_oracle_document(content,[],document_checksum=sha256(content).hexdigest(),
                               specification_checksum='a'*64,naming_checksum='b'*64)
        saved.append(json.loads(content))
        return {'oracle_id':'synthetic','document_checksum':sha256(content).hexdigest()}
    monkeypatch.setattr(oracle_fixture,'save_oracle',save)
    oracle_fixture.approved_answer(None,'task','run','spec',rows=[{'source_position':1}],approve=False)
    assert saved==[{**context,'rows':[{'source_position':1}]}]
