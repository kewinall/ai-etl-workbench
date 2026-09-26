"""Private Hop adapter primitive. Caller owns reservation and write-start gate.

Metadata must already be generated from the authorized connection and mounted
read-only. log_sink must persist through the same Run's live lease. No API route.
"""
from hashlib import sha256
import os
import stat
from .prepared_integrity import verify_prepared_files
from .hop_command import hop_command
from .managed_process import run_managed
from .hop_log_evidence import hop_log_evidence


def run_hop_cli(prepared,cancelled,*,metadata_checksum,expected_nodes,environment,log_sink):
    if os.getenv('WORKBENCH_EXECUTION_ENABLED')!='true':
        raise ValueError('EXECUTION_DISABLED')
    if not callable(log_sink):raise ValueError('PRIVATE_LOG_SINK_REQUIRED')
    verify_prepared_files(prepared)
    metadata=prepared['directory']/'metadata.json'
    info=metadata.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size>1024*1024 or getattr(info,'st_file_attributes',0)&0x400:
        raise ValueError('INVALID_HOP_METADATA')
    with metadata.open('rb') as stream:data=stream.read(1024*1024+1)
    if len(data)>1024*1024 or sha256(data).hexdigest()!=metadata_checksum:
        raise ValueError('HOP_METADATA_CHANGED')
    # Validate expected node names before starting a process.
    hop_log_evidence({'started':False,'reason':'CANCELLED','exit_code':None,'output':b''},expected_nodes)
    process=run_managed(hop_command(prepared['directory'].as_posix(),credential_launcher='WORKBENCH_VERTICA_PASSWORD' in environment,
                        source_count=2 if 'source_checksums' in prepared['binding'] else 1),cwd='/opt/hop',
                        env=environment,cancelled=cancelled,timeout_seconds=180)
    evidence=hop_log_evidence(process,expected_nodes)
    receipt=log_sink(process['output'])
    if receipt.get('checksum')!=evidence['result']['log_checksum'] or receipt.get('size')!=len(process['output']):
        raise ValueError('HOP_LOG_PERSISTENCE_MISMATCH')
    # Raw output and private paths never escape to the caller's result/event.
    return evidence
