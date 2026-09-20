from unittest.mock import MagicMock
import pytest
import app.portability_preflight as module


@pytest.mark.parametrize('database', ['isolated', 'wrong'])
def test_preflight_only_reads_and_rejects_identity_mismatch(monkeypatch, database):
    target = dict(host='test', port=5433, database='isolated', user='dbadmin', tlsmode='prefer')
    monkeypatch.setattr(module, 'destination', lambda: (target, 'synthetic-secret'))
    connect = MagicMock()
    cursor = connect.return_value.__enter__.return_value.cursor.return_value
    cursor.fetchone.side_effect = [('test-version', database), (0,)]
    monkeypatch.setattr(module.vertica_python, 'connect', connect)
    if database == 'wrong':
        with pytest.raises(ValueError, match='IDENTITY_MISMATCH'):
            module.preflight()
    else:
        result = module.preflight()
        assert result == dict(status='CONNECTED', read_only=True, version='test-version', sample_table_count=0)
        assert 'synthetic-secret' not in str(result)
    assert all(call.args[0].startswith('SELECT ') for call in cursor.execute.call_args_list)
