import json
import os
from pathlib import Path
import select
import subprocess
import sys
from uuid import uuid4

import pytest

pytest.importorskip('fcntl', reason='WSL holder requires Linux file locks and procfs')
from app.wsl_holder import status, stop


def launch(root, token):
    return subprocess.Popen([sys.executable, '-c',
        'from pathlib import Path; import sys; from app.wsl_holder import serve; serve(Path(sys.argv[1]),sys.argv[2])',
        str(root), token], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def ready(process):
    assert select.select([process.stdout], [], [], 5)[0], 'Holder did not announce startup'
    data = json.loads(process.stdout.readline())
    assert data['status'] == 'RUNNING'
    return data


def cleanup(process):
    if process.poll() is None:
        process.terminate()
        process.wait(timeout=5)


def test_single_owner_duplicate_refused_and_graceful_stop(tmp_path):
    root = tmp_path/'holder'
    token = str(uuid4())
    assert status(root)['status'] == 'NOT_STARTED'
    process = launch(root, token)
    try:
        ready(process)
        assert status(root)['token'] == token
        duplicate = launch(root, str(uuid4()))
        _, error = duplicate.communicate(timeout=5)
        assert duplicate.returncode != 0 and 'HOLDER_ALREADY_RUNNING' in error
        with pytest.raises(ValueError, match='STOP_OWNER_MISMATCH'):
            stop(root, str(uuid4()))
        assert process.poll() is None
        assert stop(root, token)['status'] == 'STOP_REQUESTED'
        process.wait(timeout=5)
        assert process.returncode == 0
        assert status(root)['status'] == 'STOPPED'
    finally:
        cleanup(process)


def test_actual_owner_death_is_lost_and_old_token_cannot_stop_replacement(tmp_path):
    root = tmp_path/'holder'
    old = str(uuid4())
    process = launch(root, old)
    try:
        ready(process)
        process.kill()
        process.wait(timeout=5)
        assert status(root)['status'] == 'LOST'
    finally:
        cleanup(process)
    new = str(uuid4())
    replacement = launch(root, new)
    try:
        ready(replacement)
        with pytest.raises(ValueError, match='STOP_OWNER_MISMATCH'):
            stop(root, old)
        assert replacement.poll() is None
        stop(root, new)
        replacement.wait(timeout=5)
        assert status(root)['token'] == new
        assert status(root)['status'] == 'STOPPED'
    finally:
        cleanup(replacement)


def test_pid_start_identity_must_match_even_when_lock_is_held(tmp_path):
    root = tmp_path/'holder'
    process = launch(root, str(uuid4()))
    try:
        data = ready(process)
        data['start_ticks'] = 'wrong-process-start'
        (root/'state.json').write_text(json.dumps(data))
        with pytest.raises(ValueError, match='OWNER_UNVERIFIED'):
            status(root)
        with pytest.raises(ValueError, match='OWNER_UNVERIFIED'):
            stop(root, data['token'])
        assert process.poll() is None
    finally:
        cleanup(process)


@pytest.mark.parametrize('kind', ['symlink', 'public'])
def test_unsafe_state_directory_rejected(tmp_path, kind):
    target = tmp_path/'target'
    target.mkdir(mode=0o700)
    root = tmp_path/'holder'
    if kind == 'symlink':
        root.symlink_to(target, target_is_directory=True)
    else:
        root.mkdir(mode=0o755)
        os.chmod(root, 0o755)
    with pytest.raises(ValueError, match='DIRECTORY_IDENTITY_REJECTED'):
        status(root)
