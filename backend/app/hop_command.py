"""Fixed Docker Hop CLI contract. No user-provided executable or extra options."""
from pathlib import PurePosixPath


def hop_command(directory, *, credential_launcher=False, source_count=1):
    # The worker supplies its private attempt directory, not an HTTP path.
    if not isinstance(directory,str) or not directory.startswith('/') or any(c in directory for c in ('\n','\r','\x00','|',';','\\')):
        raise ValueError('INVALID_HOP_ATTEMPT_DIRECTORY')
    root=PurePosixPath(directory)
    if '..' in root.parts or '.' in directory.split('/') or root==PurePosixPath('/'):
        raise ValueError('INVALID_HOP_ATTEMPT_DIRECTORY')
    if type(source_count) is not int or source_count not in (1,2):
        raise ValueError('INVALID_HOP_SOURCE_COUNT')
    parameters = ('SOURCE_CSV='+str(root/'source.csv') if source_count == 1 else
                  ';'.join(f'SOURCE_CSV_{index}='+str(root/f'source-{index}'/'source.csv') for index in range(2)))
    launcher = ['/usr/bin/java', '-Xmx2048m', '-DHOP_SHARED_JDBC_FOLDERS=/opt/hop/lib/jdbc',
                '-DHOP_PLATFORM_RUNTIME=Run', '-DHOP_AUTO_CREATE_CONFIG=Y',
                '-cp', '/opt/hop/lib/core/*:/opt/hop/lib/beam/*:/opt/hop/lib/swt/linux/x86_64/*',
                '/app/backend/app/java/WorkbenchHopRun.java'] if credential_launcher else ['/opt/hop/hop-run.sh']
    return [*launcher, '--file='+str(root/'candidate.hpl'),
            '--metadata-export='+str(root/'metadata.json'), '--runconfig=local',
            '--level=BASIC', '--parameters-separator=;',
            '--parameters='+parameters]
