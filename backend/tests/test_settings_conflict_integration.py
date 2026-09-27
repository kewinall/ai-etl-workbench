"""Real isolated PostgreSQL optimistic concurrency; never use Pilot settings."""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from uuid import uuid4
from app.repository import PostgresRepository, SettingsConflict
from test_run_queue_integration import context

pytestmark=pytest.mark.skipif(os.getenv('WORKBENCH_ALLOW_DATABASE_TESTS')!='1',reason='Isolated PostgreSQL required')

def test_connection_secret_first_write_and_stale_write_are_serialized(context):
    repo=PostgresRepository(os.environ['DATABASE_URL'])
    ref='connection:synthetic-'+uuid4().hex
    barrier=Barrier(2)
    try:
        assert repo.secret_version(ref) is None
        def create(index):
            barrier.wait()
            try:
                repo.save_secret(ref,f'cipher-{index}'.encode(),b'synthetic-nonce',expected_version='missing')
                return index
            except SettingsConflict:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            winners=[i for i in pool.map(create,range(2)) if i is not None]
        assert len(winners)==1
        version=repo.secret_version(ref)
        repo.save_secret(ref,b'new-cipher',b'new-nonce',expected_version=version)
        with pytest.raises(SettingsConflict):
            repo.save_secret(ref,b'rejected',b'rejected',expected_version=version)
        with repo.conn() as conn:
            row=conn.execute('select cipher_text,nonce from platform.secret_vault_entry where secret_ref=%s',(ref,)).fetchone()
            assert bytes(row['cipher_text'])==b'new-cipher'
            assert bytes(row['nonce'])==b'new-nonce'
    finally:
        with repo.conn() as conn:
            conn.execute('delete from platform.secret_vault_entry where secret_ref=%s',(ref,))

def test_profile_updates_allow_only_one_writer_for_each_version(context):
    from app.ai_profile_api import ProfileConflict
    queue,task_id=context
    repo=PostgresRepository(os.environ['DATABASE_URL'])
    project=repo.get_project(repo.get_task(task_id)['project_id'])
    original=repo.ai_profile(project['default_ai_profile'])
    version=original['updated_at'].isoformat()
    barrier=Barrier(2)
    def update(index):
        barrier.wait()
        try:
            repo.upsert_ai_profile({**original,'display_name':f'Synthetic writer {index}','_expected_version':version})
            return index
        except ProfileConflict:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(update,range(2)))
    winners=[i for i in results if i is not None]
    assert len(winners)==1
    current=repo.ai_profile(original['profile_id'])
    assert current['display_name']==f'Synthetic writer {winners[0]}'
    assert current['secret_ref']==original['secret_ref']
    with pytest.raises(ProfileConflict):
        repo.upsert_ai_profile({**original,'_expected_version':version})

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

def test_profile_secret_conflict_leaves_vault_unchanged(context):
    from app.ai_profile_api import ProfileConflict
    queue,task_id=context
    repo=PostgresRepository(os.environ['DATABASE_URL'])
    project=repo.get_project(repo.get_task(task_id)['project_id'])
    original=repo.ai_profile(project['default_ai_profile'])
    ref=f"ai-profile:{original['profile_id']}"
    try:
        first=repo.upsert_ai_profile({**original,'provider_type':'LITELLM_BEDROCK'})
        stale=first['updated_at'].isoformat()
        current=repo.upsert_ai_profile({**first,'display_name':'Concurrent newer profile','_expected_version':stale})
        with pytest.raises(ProfileConflict):
            repo.update_ai_profile_secret(original['profile_id'],b'synthetic-cipher',b'synthetic-nonce',stale)
        with repo.conn() as conn:
            assert conn.execute('select 1 from platform.secret_vault_entry where secret_ref=%s',(ref,)).fetchone() is None
        repo.update_ai_profile_secret(original['profile_id'],b'synthetic-cipher',b'synthetic-nonce',current['updated_at'].isoformat())
        result=repo.ai_profile(original['profile_id'])
        assert result['display_name']=='Concurrent newer profile'
        assert result['secret_ref']==ref
        with pytest.raises(ProfileConflict):
            repo.update_ai_profile_secret(original['profile_id'],b'rejected',b'rejected',current['updated_at'].isoformat())
        with repo.conn() as conn:
            stored=conn.execute('select cipher_text from platform.secret_vault_entry where secret_ref=%s',(ref,)).fetchone()
            assert bytes(stored['cipher_text'])==b'synthetic-cipher'
    finally:
        with repo.conn() as conn:
            conn.execute('update platform.ai_provider_profile set secret_ref=%s where profile_id=%s',(original['secret_ref'],original['profile_id']))
            conn.execute('delete from platform.secret_vault_entry where secret_ref=%s',(ref,))
