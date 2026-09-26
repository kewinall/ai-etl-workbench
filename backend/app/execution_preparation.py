"""Combine approved specification and verified source; no execution permission."""
from contextlib import contextmanager
from hashlib import sha256
from .approved_candidate import load_approved_candidate
from .source_staging import stage_csv_source, stage_csv_sources
from .source_binding import source_set_checksum
from .prepared_integrity import verify_prepared_files


@contextmanager
def prepare_approved_source(queue, task_id, run_id, specification_id):
    with queue.conn() as conn:
        candidate = load_approved_candidate(queue, conn, task_id, run_id, specification_id)
    config = candidate['run']['input_snapshot']['source_config']
    sources = config.get('sources') or []
    multi = candidate['compiled']['specification']['version'] == 2
    if len(sources) != (2 if multi else 1) or any(source.get('type') != 'CSV' or not source.get('upload_id') for source in sources):
        raise ValueError('VERIFIED_UPLOADED_CSV_REQUIRED')
    staging = stage_csv_sources(run_id, config) if multi else stage_csv_source(run_id, sources[0], config.get('csv_input_contract_v1'))
    with staging as staged:
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
        paths = ({'source_paths': {ref: item['path'] for ref,item in staged['sources'].items()}} if multi else
                 {'source_path': staged['path']})
        checksums = {ref: item['evidence']['content_checksum'] for ref,item in staged['sources'].items()} if multi else None
        source_binding = ({'source_checksums': checksums, 'source_checksum': source_set_checksum(checksums)} if multi else
                          {'source_checksum': staged['evidence']['content_checksum']})
        prepared = {'status':'PREPARED_NOT_AUTHORIZED', 'execution_authorized':False,
               **paths, 'hpl_path':hpl, 'directory':staged['directory'],
               'binding':{'run_id':str(run_id), 'specification_id':str(specification_id),
                          'specification_checksum':current['specification_checksum'],
                          'approval_id':current['approval_id'],
                          'input_checksum':current['run']['input_checksum'],
                          'settings_checksum':current['run']['settings_snapshot']['checksum'],
                          'hpl_checksum':current['compiled']['hpl_checksum'],
                          **source_binding}}
        verify_prepared_files(prepared)
        yield prepared
