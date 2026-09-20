"""Resolve compiler-owned bytes and QA-linked SDM. Internal candidate only."""
import os
from contextlib import nullcontext
from hashlib import sha256
from .delivery_context import load_delivery_context
from .specification_store import context
from .delivery_compiler import compile_delivery_components,build_checked_bundle_candidate
from .release_bundle import BundleArtifact
from .release_content_gate import check_release_content
from .sdm_files import read_sdm_bytes
from .target_ownership import check_target_claim
from .release_secret_screen import run_forbidden_values


def assemble_release_candidate(queue,task_id,run_id,sdm_id,expected_qa_checksum,*,repo,root=None,connection=None):
    with (nullcontext(connection) if connection is not None else queue.conn()) as conn:
        delivery=load_delivery_context(queue,task_id,run_id,connection=conn)
        if delivery['qa_binding_checksum']!=expected_qa_checksum:raise ValueError('RELEASE_QA_VERSION_CONFLICT')
        row=conn.execute('''SELECT s.* FROM platform.sdm_artifact s JOIN platform.sdm_qa_binding b USING(sdm_id)
            WHERE s.task_id=%s AND s.run_id=%s AND s.sdm_id=%s AND b.run_id=s.run_id AND b.qa_approval_id=%s''',
            (task_id,run_id,sdm_id,delivery['qa_approval_id'])).fetchone()
        if not row or row['specification_checksum']!=delivery['specification_checksum']:
            raise ValueError('RELEASE_QA_LINKED_SDM_REQUIRED')
        run,naming=context(queue,conn,task_id,run_id)
        document_run={**run,'write_started':False}
        compiled=compile_delivery_components(delivery['specification'],document_run,naming)
        auth=conn.execute('SELECT binding FROM platform.task_run_execution_authorization WHERE run_id=%s',(run_id,)).fetchone()['binding']
        claim=check_target_claim(queue,auth)
        if (compiled.get('hpl_checksum')!=auth.get('hpl_checksum') or compiled.get('ddl_checksum')!=claim['ddl_checksum']):
            raise ValueError('RELEASE_EXECUTED_COMPONENTS_CHANGED')
        storage=root if root is not None else os.getenv('WORKBENCH_ARTIFACT_ROOT')
        if not storage:raise ValueError('SDM_STORAGE_NOT_CONFIGURED')
        sdm=read_sdm_bytes(storage,row['project_id'],run_id,sdm_id,checksum=row['checksum'],file_size=row['file_size'])
        content={kind:compiled[kind.lower()].encode() for kind in ('HPL','HWF','DDL','PARAMETERS')}
        content['SDM']=sdm
        artifacts=[BundleArtifact(kind,data,sha256(data).hexdigest(),str(run_id),delivery['specification_checksum'],naming['checksum']) for kind,data in content.items()]
        with run_forbidden_values(repo,run['settings_snapshot']) as forbidden:
            screening=check_release_content(artifacts,forbidden_values=forbidden)
        result=build_checked_bundle_candidate(artifacts,delivery['specification'],document_run,naming)
        return {**result,'content_screen':screening,'qa_approval_id':delivery['qa_approval_id'],
            'limitations':['ONLY_RUN_SCOPED_VAULT_VALUES_SCREENED','DESTINATION_EXECUTION_NOT_VERIFIED','RELEASE_APPROVAL_NOT_RECORDED']}
