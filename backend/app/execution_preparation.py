"""Combine approved specification and verified source; no execution permission."""
from contextlib import contextmanager
from hashlib import sha256
from .approved_candidate import load_approved_candidate
from .source_staging import stage_csv_source
from .prepared_integrity import verify_prepared_files


@contextmanager
def prepare_approved_source(queue, task_id, run_id, specification_id):
    with queue.conn() as conn:
        candidate = load_approved_candidate(queue, conn, task_id, run_id, specification_id)
    config = candidate['run']['input_snapshot']['source_config']
    sources = config.get('sources') or []
    if len(sources) != 1 or sources[0].get('type') != 'CSV' or not sources[0].get('upload_id'):
        raise ValueError('VERIFIED_UPLOADED_CSV_REQUIRED')
    with stage_csv_source(run_id, sources[0], config.get('csv_input_contract_v1')) as staged:
        # Do not hold database locks during file I/O. Revalidate afterwards;
        # a future dispatcher must STILL atomically reserve its own permission.
        with queue.conn() as conn:
            current = load_approved_candidate(queue, conn, task_id, run_id, specification_id)
            if any(current[key] != candidate[key] for key in ('approval_id','specification_checksum')):
                raise ValueError('PREPARATION_CHANGED')
            if current['compiled']['hpl_checksum'] != candidate['compiled']['hpl_checksum']:
                raise ValueError('PREPARATION_CHANGED')
        hpl = staged['directory'] / 'candidate.hpl'
        with hpl.open('x', encoding='utf-8', newline='') as stream:
            stream.write(current['compiled']['hpl'])
        if sha256(hpl.read_bytes()).hexdigest() != current['compiled']['hpl_checksum']:
            raise ValueError('PREPARED_HPL_CHECKSUM_MISMATCH')
        prepared = {'status':'PREPARED_NOT_AUTHORIZED', 'execution_authorized':False,
               'source_path':staged['path'], 'hpl_path':hpl, 'directory':staged['directory'],
               'binding':{'run_id':str(run_id), 'specification_id':str(specification_id),
                          'specification_checksum':current['specification_checksum'],
                          'approval_id':current['approval_id'],
                          'input_checksum':current['run']['input_checksum'],
                          'settings_checksum':current['run']['settings_snapshot']['checksum'],
                          'hpl_checksum':current['compiled']['hpl_checksum'],
                          'source_checksum':staged['evidence']['content_checksum']}}
        verify_prepared_files(prepared)
        yield prepared
