from contextlib import contextmanager
import pytest
from app import developer_api


@pytest.mark.parametrize('code,expected', [
    ('DEVELOPER_NAMING_CONFIRMATION_REQUIRED', '命名對照'),
    ('DEVELOPER_SA_APPROVAL_REQUIRED', 'SA 需求審查'),
    ('private connection details', '前置證據無法確認'),
])
def test_missing_context_explains_gate_without_leaking_error(monkeypatch,code,expected):
    class Result:
        def __init__(self,value):self.value=value
        def fetchone(self):return self.value
    class Connection:
        def execute(self,query,args):
            return Result({'settings_snapshot':{'ai':{'provider_type':'LOCAL_COPILOT'},'model_routes':{'etl_specification':'copilot/test'}}} if 'platform.task_run' in query else None)
    class Queue:
        @contextmanager
        def conn(self):yield Connection()
        def locked_task(self,*args):return {}
    def blocked(*args):raise ValueError(code)
    monkeypatch.setattr(developer_api,'load_context',blocked)
    value=developer_api.read(Queue(),'TASK-TEST','test-run')
    assert expected in value['blocked_reason']
    assert not value['eligible'] and value['invocation'] is None
    assert 'private connection details' not in str(value)
