import pytest
from app.recovery_verify import check_scope


def test_explicit_loopback_restore_scope():
    check_scope('postgresql://workbench@127.0.0.1/restore_full_055', 'isolated-copy-v1')


@pytest.mark.parametrize('url', [
    'postgresql://workbench@postgres/workbench',
    'postgresql://workbench@127.0.0.1/workbench',
    'postgresql://workbench:private@127.0.0.1/restore_test',
    'postgresql://workbench@127.0.0.1/restore_test?host=postgres',
    'postgresql://workbench@localhost/restore_test',
    'postgresql://other@127.0.0.1/restore_test',
])
def test_reject_wrong_scope(url):
    with pytest.raises(ValueError, match='RECOVERY_SCOPE_REQUIRED'):
        check_scope(url, 'isolated-copy-v1')


def test_requires_opt_in():
    with pytest.raises(ValueError):
        check_scope('postgresql://workbench@127.0.0.1/restore_test', None)
