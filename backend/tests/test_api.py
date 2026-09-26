from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)
def test_health(): assert client.get('/api/health').json()['status']=='ok'
def test_dashboard(): assert client.get('/api/dashboard').status_code==200
def test_create_task_validation_without_database_mutation():
    r=client.post('/api/tasks',json={'name':'x','requirement':'bad'})
    assert r.status_code==422
def test_missing_task(): assert client.get('/api/tasks/nope').status_code==404


def test_create_two_csv_task_and_qualified_naming_through_normal_api(tmp_path,monkeypatch):
    from uuid import uuid4
    from app import task_uploads
    monkeypatch.setattr(task_uploads,'ROOT',tmp_path)
    monkeypatch.setattr(task_uploads,'UPLOAD_ROOT',tmp_path/'uploads')
    project=client.post('/api/projects',json={'project_name':'Join API '+str(uuid4())})
    assert project.status_code==201,project.text
    sources=[]
    for index,content in enumerate(('客戶編號,名稱\nA,left\n','客戶編號|名稱\nA|right\n')):
        uploaded=client.post('/api/task-sources/upload',files={'file':(f'source{index}.csv',content.encode(),'text/csv')})
        assert uploaded.status_code==200,uploaded.text
        sources.append({**uploaded.json(),'type':'CSV','has_actual_data':True,'alias':f'src{index}'})
    created=client.post('/api/projects/'+project.json()['project_id']+'/tasks',json={
        'name':'two CSV API test','requirement':'保留左側所有客戶，以客戶編號 LEFT JOIN',
        'category':'DW_DM','source_type':'CSV','source_config':{'sources':sources},
        'target_schema':'ai_sample','target_table':'join_api_test'})
    assert created.status_code==201,created.text
    task=created.json()
    suggested=client.post('/api/tasks/'+task['id']+'/naming-contract/suggest')
    assert suggested.status_code==200,suggested.text
    columns=suggested.json()['contract']['columns']
    assert [c['source_name'] for c in columns]==[
        'source.0.客戶編號','source.0.名稱','source.1.客戶編號','source.1.名稱']
    assert len({c['english_name'] for c in columns})==4
    confirmed=client.post('/api/tasks/'+task['id']+'/naming-contract/confirm',json={'columns':columns})
    assert confirmed.status_code==200,confirmed.text
    reloaded=client.get('/api/tasks/'+task['id']+'/naming-contract').json()['contract']
    assert reloaded is not None


def test_dw_dm_rejects_unsupported_source_shapes_before_creation():
    for kinds in (['CSV'],['CSV','CSV','CSV'],['CSV','VERTICA'],['CSV','EXCEL']):
        response=client.post('/api/tasks',json={'name':'invalid sources','requirement':'invalid source mix',
            'category':'DW_DM','source_config':{'sources':[{'type':kind} for kind in kinds]}})
        assert response.status_code==422,response.text
