import pytest
from app.hop_command import hop_command


def test_private_launcher_never_carries_secret_in_arguments():
    args=hop_command('/app/runtime-temp/run-sources/test',credential_launcher=True)
    assert args[0]=='/usr/bin/java'
    assert '/app/backend/app/java/WorkbenchHopRun.java' in args
    assert not any('PASSWORD' in arg for arg in args)
    assert '--parameters=SOURCE_CSV=/app/runtime-temp/run-sources/test/source.csv' in args


def test_paths_remain_literal_arguments():
    args=hop_command('/app/runtime-temp/run-sources/attempt with spaces,comma')
    assert args[0]=='/opt/hop/hop-run.sh'
    assert args[-1]=='--parameters=SOURCE_CSV=/app/runtime-temp/run-sources/attempt with spaces,comma/source.csv'
    assert '--parameters-separator=;' in args
    assert '--runconfig=local' in args and '--level=BASIC' in args
    assert len(args)==7


@pytest.mark.parametrize('path',['relative','/','/tmp/../other','/tmp/./other','/tmp/a|PASSWORD=x','/tmp/a\nb','C:\\tmp',None])
def test_ambiguous_or_parameter_injecting_path_rejected(path):
    with pytest.raises(ValueError,match='INVALID_HOP_ATTEMPT_DIRECTORY'):
        hop_command(path)


@pytest.mark.parametrize('private', [False, True])
def test_excel_fixed_parameter_and_filename(private):
    args = hop_command('/candidate with spaces,comma', credential_launcher=private, source_format='XLSX')
    assert args[-1] == '--parameters=SOURCE_XLSX=/candidate with spaces,comma/source.xlsx'
    assert not any('SOURCE_CSV' in arg for arg in args)


@pytest.mark.parametrize('kind,count', [('EXCEL', 1), ('xlsx', 1), (None, 1), ('XLSX', 2), ('CSV;PASSWORD=x', 1)])
def test_unsupported_source_format_is_rejected(kind, count):
    with pytest.raises(ValueError, match='INVALID_HOP_SOURCE_FORMAT'):
        hop_command('/candidate', source_format=kind, source_count=count)
