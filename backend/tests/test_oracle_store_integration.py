import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID,uuid4
import psycopg
import pytest
from test_run_queue_integration import context
from test_specification_api_integration import prepared,pytestmark
from app.oracle_store import save_oracle,read_oracle,approve_oracle
from app.oracle_api import create_oracle_router


def test_oracle_versions_encrypted_immutable_and_scoped(context):
    queue,task_id,run,spec,naming,api=prepared(context)
    api.app.include_router(create_oracle_router(queue))
    base=f'/api/tasks/{task_id}/runs/{run["run_id"]}/specifications'
    saved=api.post(base,json=spec).json();sid=UUID(saved['specification_id'])
    doc={'version':1,'specification_checksum':saved['content_checksum'],'naming_checksum':naming['checksum'],
         'columns':[{'name':'category','kind':'TEXT','nullable':False},{'name':'total_amount','kind':'DECIMAL','nullable':False},{'name':'row_count','kind':'INTEGER','nullable':False}],
         'rows':[{'category':'A','total_amount':'301.35','row_count':2}]}
    content=json.dumps(doc).encode()
    editor_url=base+'/'+str(sid)+'/oracle-editor-context'
    assert api.get(editor_url).status_code==409
    with pytest.raises(ValueError,match='SPECIFICATION_APPROVAL_REQUIRED'):
        save_oracle(queue,task_id,run['run_id'],sid,content)
    assert api.post(base+'/'+str(sid)+'/approve',json={'content_checksum':saved['content_checksum']}).status_code==200
    editor=api.get(editor_url)
    assert editor.status_code==200
    assert editor.json()['columns']==doc['columns']
    assert editor.json()['specification_checksum']==saved['content_checksum']
    assert editor.json()['naming_checksum']==naming['checksum']
    assert editor.json()['execution_authorized'] is False
    too_wide={**doc,'rows':[{'category':'中'*11,'total_amount':'301.35','row_count':2}]}
    with pytest.raises(ValueError,match='ORACLE_TEXT_WIDTH_EXCEEDED'):
        save_oracle(queue,task_id,run['run_id'],sid,json.dumps(too_wide).encode())
    too_precise={**doc,'rows':[{'category':'A','total_amount':'301.351','row_count':2}]}
    with pytest.raises(ValueError,match='ORACLE_DECIMAL_SCALE_EXCEEDED'):
        save_oracle(queue,task_id,run['run_id'],sid,json.dumps(too_precise).encode())
    assert api.get(editor_url.replace(task_id,'other-task')).status_code in (404,409)
    wrong={**doc,'columns':[dict(column) for column in doc['columns']],'rows':[]}
    wrong['columns'][1]['kind']='TEXT'
    with pytest.raises(ValueError,match='ORACLE_OUTPUT_TYPE_MISMATCH'):
        save_oracle(queue,task_id,run['run_id'],sid,json.dumps(wrong).encode())
    barrier=Barrier(2)
    def concurrent_save(_):
        barrier.wait(timeout=5)
        return save_oracle(queue,task_id,run['run_id'],sid,content)
    with ThreadPoolExecutor(max_workers=2) as pool:
        simultaneous=list(pool.map(concurrent_save,range(2)))
    assert simultaneous[0]==simultaneous[1]
    first=simultaneous[0]
    assert first['version']==1 and first['qa_passed'] is False
    assert save_oracle(queue,task_id,run['run_id'],sid,content)==first
    assert read_oracle(queue,task_id,run['run_id'],sid,first['oracle_id'])==content
    with pytest.raises(ValueError,match='CURRENT_ORACLE_CHECKSUM_REQUIRED'):
        approve_oracle(queue,task_id,run['run_id'],sid,first['oracle_id'],'c'*64)
    oracle_url=base+'/'+str(sid)+'/oracles'
    response=api.post(oracle_url+'/'+first['oracle_id']+'/approve',json={'document_checksum':first['document_checksum'],'confirmed':True})
    assert response.status_code==200
    approved=response.json()
    assert approved['qa_passed'] is False
    assert approve_oracle(queue,task_id,run['run_id'],sid,first['oracle_id'],first['document_checksum'])==approved
    doc['rows'][0]['total_amount']='302.35'
    response=api.post(oracle_url,json={'document':json.dumps(doc)})
    assert response.status_code==201
    second=response.json()
    assert second['version']==2
    history=api.get(oracle_url)
    assert history.status_code==200
    items=history.json()['items']
    assert [item['version'] for item in items]==[2,1]
    assert [item['approval_recorded'] for item in items]==[False,True]
    assert all(item['eligibility']=='NOT_EVALUATED' and not item['qa_passed'] and not item['release_ready'] for item in items)
    assert set(items[0])=={'oracle_id','version','document_checksum','specification_checksum','naming_checksum','created_at','approval_id','approved_at','approval_recorded','eligibility','qa_passed','release_ready'}
    assert api.get(oracle_url.replace(task_id,'other-task')).status_code==409
    with pytest.raises(ValueError,match='CURRENT_ORACLE_CHECKSUM_REQUIRED'):
        approve_oracle(queue,task_id,run['run_id'],sid,first['oracle_id'],first['document_checksum'])
    with queue.conn() as conn:
        assert conn.execute('SELECT count(*) AS n FROM platform.result_oracle_approval WHERE oracle_id=%s',(second['oracle_id'],)).fetchone()['n']==0
    assert read_oracle(queue,task_id,run['run_id'],sid,first['oracle_id'])==content
    with pytest.raises(ValueError,match='ORACLE_NOT_FOUND'):
        read_oracle(queue,'other-task',run['run_id'],sid,first['oracle_id'])
    with queue.conn() as conn:
        row=conn.execute('SELECT * FROM platform.result_oracle WHERE oracle_id=%s',(first['oracle_id'],)).fetchone()
        assert content not in bytes(row['cipher_text'])
        assert 'rows' not in row
    with pytest.raises(psycopg.Error):
        with queue.conn() as conn:
            conn.execute('UPDATE platform.result_oracle SET size=size+1 WHERE oracle_id=%s',(first['oracle_id'],))
    with pytest.raises(psycopg.Error):
        with queue.conn() as conn:
            conn.execute('UPDATE platform.result_oracle_approval SET document_checksum=%s WHERE oracle_id=%s',('d'*64,first['oracle_id']))
    newer=api.post(base,json={**spec,'filters':[]})
    assert newer.status_code==200
    assert newer.json()['specification_id']!=str(sid)
    assert api.get(editor_url).status_code==409
    assert api.get(oracle_url).json()==history.json()
    assert api.get(base+'/'+newer.json()['specification_id']+'/oracles').json()=={'items':[]}
    review_url=oracle_url+'/'+first['oracle_id']+'/review'
    reviewed=api.get(review_url)
    assert reviewed.status_code==200
    assert reviewed.headers['cache-control']=='no-store'
    assert reviewed.json()['rows']==[{'category':'A','total_amount':'301.35','row_count':'2'}]
    assert reviewed.json()['document_checksum']==first['document_checksum']
    assert reviewed.json()['view']=='HISTORICAL_READ_ONLY'
    assert api.get(review_url+'?offset=1&limit=1').json()['rows']==[]
    assert api.get(review_url+'?limit=101').status_code==422
    assert api.get(review_url.replace(task_id,'other-task')).status_code==409
    with pytest.raises(ValueError,match='CURRENT_SPECIFICATION_REQUIRED'):
        approve_oracle(queue,task_id,run['run_id'],sid,second['oracle_id'],second['document_checksum'])
    with pytest.raises(ValueError,match='CURRENT_SPECIFICATION_REQUIRED'):
        save_oracle(queue,task_id,run['run_id'],sid,content)
    assert read_oracle(queue,task_id,run['run_id'],sid,first['oracle_id'])==content
