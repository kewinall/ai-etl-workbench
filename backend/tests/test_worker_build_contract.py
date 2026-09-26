"""Static source guard; actual Docker builds are separate acceptance evidence."""
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(not (ROOT / 'deploy/compose.yml').is_file(),
                              reason='Deployment source checkout required')


def test_worker_uses_explicit_jdbc_context_and_checksum_not_local_database_image():
    source = (ROOT / 'deploy/Dockerfile.backend').read_text()
    assert 'FROM local/vertica' not in source
    assert 'COPY --from=vertica-jdbc /vertica-jdbc.jar' in source
    assert 'sha256sum --check --strict' in source
    assert 'COPY --from=vertica-driver' in source


def test_both_worker_profiles_supply_jdbc_context():
    compose = yaml.safe_load((ROOT / 'deploy/compose.yml').read_text())
    for name in ('worker', 'pilot-hop-worker'):
        build = compose['services'][name]['build']
        assert build['target'] == 'worker'
        assert 'WORKBENCH_JDBC_DIR' in build['additional_contexts']['vertica-jdbc']
