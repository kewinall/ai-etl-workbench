"""Replay orchestration with real staged files, fake DB/engine; not E2E proof."""
from contextlib import nullcontext
from unittest.mock import MagicMock
from uuid import uuid4
import pytest
from app import release_replay_worker as module, task_uploads
from app.delivery_compiler import compile_delivery_components
from app.release_bundle import MEMBERS
from app.source_binding import execution_sources
from app.sa_contract import digest
from test_join_semantics import join_design


@pytest.mark.parametrize('changed', [False,True])
def test_replay_binds_both_staged_sources_before_claim(tmp_path,monkeypatch,changed):
    monkeypatch.setattr(task_uploads,'ROOT',tmp_path)
    monkeypatch.setattr(task_uploads,'UPLOAD_ROOT',tmp_path/'uploads')
    spec,run,naming = join_design()
    config = run['input_snapshot']['source_config']
    for i,text in enumerate(('客戶編號,名稱\nA,left\n','客戶編號|名稱\nA|right\n')):
        fields = config['sources'][i]['fields']
        config['sources'][i] = {**task_uploads.save_and_profile(f'{i}.csv',text.encode()),
                               'type':'CSV','has_actual_data':True,'fields':fields}
    compiled = compile_delivery_components(spec,run,naming)
    parts = {MEMBERS[k]:compiled[k.lower()].encode() for k in ('HPL','HWF','DDL','PARAMETERS')}
    candidate = {'checksum':'c'*64,'manifest':{'artifacts':[
        {'type':k,'checksum':compiled[k.lower()+'_checksum']} for k in ('HPL','HWF','DDL')]}}
    binding = execution_sources(config,2)
    if changed: binding['source_checksums']['source.1'] = '0'*64
    conn = MagicMock()
    def execute(sql,*args):
        row = {'binding':binding} if sql.startswith('SELECT binding') else {'check_id':uuid4()}
        return MagicMock(fetchone=lambda:row)
    conn.execute.side_effect = execute
    queue = MagicMock();queue.conn.side_effect = lambda:nullcontext(conn)
    run['settings_snapshot']['connection'] = dict(host='original',port=5433,database='original')
    monkeypatch.setattr(module,'destination',lambda:(dict(type='VERTICA',host='isolated',port=5433,
        database='isolated',user='test',tlsmode='disable'),'synthetic-secret'))
    monkeypatch.setattr(module,'load_bound_result_query',lambda *a:({},
        {'content':'{"columns":[]}','document_checksum':'a'*64}))
    monkeypatch.setattr(module,'replay_context',lambda *a:(candidate,parts,run,spec))
    db = MagicMock();db.__enter__.return_value = db;db.cursor.return_value.fetchone.return_value = None
    monkeypatch.setattr(module.vertica_python,'connect',lambda **k:db)
    commands=[]
    def command(directory,**kwargs):
        from pathlib import Path
        path=Path(directory)
        assert (path/'source-0/source.csv').is_file() and (path/'source-1/source.csv').is_file()
        commands.append(kwargs)
        return ['synthetic-hop','--file=candidate.hpl']
    monkeypatch.setattr(module,'hop_command',command)
    monkeypatch.setattr(module,'run_managed',lambda *a,**k:{'output':b'synthetic-log'})
    monkeypatch.setattr(module,'workflow_log_evidence',lambda *a:{'result':{'status':'COMPLETED','log_checksum':'e'*64},'workflow_completed':True})
    monkeypatch.setattr(module,'execute_bound_result_query',lambda *a:None)
    monkeypatch.setattr(module,'read_result_rows',lambda *a:[])
    monkeypatch.setattr(module,'compare_oracle_document',lambda *a,**k:dict(status='MATCH',
        expected_checksum='f'*64,actual_checksum='f'*64,expected_count=0,actual_count=0))
    if changed:
        with pytest.raises(ValueError,match='PORTABILITY_EXECUTED_SOURCE_CHANGED'):
            module.replay(queue,None,'task',run['run_id'],uuid4(),root=tmp_path)
        assert commands == [] and all(call.args[0].startswith('SELECT') for call in conn.execute.call_args_list)
    else:
        result=module.replay(queue,None,'task',run['run_id'],uuid4(),root=tmp_path)
        assert result['status'] == 'PASS' and not result['release_ready']
        assert commands == [{'credential_launcher':True,'source_count':2}]
        update = next(call for call in conn.execute.call_args_list if call.args[0].startswith('UPDATE'))
        proof=update.args[1][1].obj
        assert proof['version'] == 2 and proof['source_checksums'] == binding['source_checksums']
        assert proof['source_checksum'] == binding['source_checksum'] and digest(proof) == result['checksum']
