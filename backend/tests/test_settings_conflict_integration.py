"""Real isolated PostgreSQL optimistic concurrency; never use Pilot settings."""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from app.repository import PostgresRepository, SettingsConflict
from test_run_queue_integration import context

pytestmark=pytest.mark.skipif(os.getenv('WORKBENCH_ALLOW_DATABASE_TESTS')!='1',reason='Isolated PostgreSQL required')

def test_stale_and_simultaneous_group_updates_do_not_overwrite(context):
    repo=PostgresRepository(os.environ['DATABASE_URL'])
    key='execution_tool_paths'
    original=next((r for r in repo.settings() if r['key']==key),None)
    try:
        repo.update_setting(key,{'hop_run_path':'/synthetic/initial'})
        version=next(r['updated_at'] for r in repo.settings() if r['key']==key)
        barrier=Barrier(2)
        def update(index):
            barrier.wait()
            try:
                repo.update_setting(key,{'hop_run_path':f'/synthetic/{index}'},expected_version=version)
                return index
            except SettingsConflict:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(update,range(2)))
        winners=[r for r in results if r is not None]
        assert len(winners)==1
        expected={'hop_run_path':f'/synthetic/{winners[0]}'}
        assert repo.setting(key)==expected
        with pytest.raises(SettingsConflict):
            repo.update_setting(key,{'hop_run_path':'/synthetic/stale'},expected_version=version)
        assert repo.setting(key)==expected
    finally:
        with repo.conn() as conn:
            if original:
                import json
                conn.execute('update platform.system_setting set setting_value=%s,updated_at=%s where setting_key=%s',(json.dumps(original['value']),original['updated_at'],key))
            else:
                conn.execute('delete from platform.system_setting where setting_key=%s',(key,))
