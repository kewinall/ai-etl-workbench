from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)
def test_health(): assert client.get('/api/health').json()['status']=='ok'
def test_dashboard(): assert client.get('/api/dashboard').status_code==200
def test_create_task_validation_without_database_mutation():
    r=client.post('/api/tasks',json={'name':'x','requirement':'bad'})
    assert r.status_code==422
def test_missing_task(): assert client.get('/api/tasks/nope').status_code==404
