"""Adapter for hop_worker.execute_once, not a dispatcher or permission grant."""
import os
from xml.etree import ElementTree as ET
from .hop_connection_runtime import connection_runtime
from .hop_cli import run_hop_cli
from .prepared_integrity import verify_prepared_files
from .target_ownership import check_target_claim
from .target_preflight import verify_empty_target, require_empty_check


def vertica_executor(repo, settings_snapshot):
    def execute(prepared, cancelled, log_sink):
        if os.getenv('WORKBENCH_EXECUTION_ENABLED') != 'true':
            raise ValueError('EXECUTION_DISABLED')
        verify_prepared_files(prepared)
        check_target_claim(repo, prepared['binding'])
        require_empty_check(repo, prepared['binding'])
        checksum = prepared['binding']['settings_checksum']
        with connection_runtime(repo, settings_snapshot, checksum) as runtime:
            path = prepared['directory'] / 'metadata.json'
            # Staging owns cleanup. Never overwrite an existing metadata file.
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w', encoding='utf-8', newline='') as stream:
                stream.write(runtime['metadata'])
            root = ET.fromstring(prepared['hpl_path'].read_bytes())
            names = [node.findtext('name') for node in root.findall('transform')]
            # Do not inherit platform PG, AI credentials, Java injection flags,
            # or unrelated host configuration into the ETL child.
            environment = {key: os.environ[key] for key in ('PATH', 'HOME', 'JAVA_HOME', 'LANG', 'LC_ALL') if key in os.environ}
            environment.update(HOP_HOME='/opt/hop', HOP_SHARED_JDBC_FOLDERS='/opt/hop/lib/jdbc', **runtime['environment'])
            try:
                evidence = run_hop_cli(prepared, cancelled, metadata_checksum=runtime['metadata_checksum'],
                    expected_nodes=names, environment=environment, log_sink=log_sink)
                return evidence['result']
            finally:
                environment.clear()
    execute.preflight = lambda prepared: verify_empty_target(repo, prepared['binding'], settings_snapshot)
    return execute
