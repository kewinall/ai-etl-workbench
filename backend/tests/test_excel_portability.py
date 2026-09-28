"""Strict format binding of isolated replay evidence; not runtime acceptance."""
import pytest
from app.release_portability import validate_portability
from app.sa_contract import digest
from test_formal_release_bundle import proof_fixture


def fixture():
    candidate,row=proof_fixture()
    row['evidence'].update(version=4,source_format='XLSX')
    row['checksum']=digest(row['evidence'])
    return candidate,row


def check(candidate,row,**changes):
    options=dict(expected_checksum='f'*64,expected_count=1,source_format='XLSX')
    return validate_portability(row,candidate,'d'*64,**{**options,**changes})


def test_excel_proof_requires_explicit_format_and_single_source():
    candidate,row=fixture()
    assert check(candidate,row)['version']==4
    for changes in (dict(source_format=None),dict(source_format='CSV'),dict(source_format='JSON'),
                    dict(source_checksums={'source.0':'d'*64}),dict(source_order={}),
                    dict(result_query_checksum='0'*64)):
        with pytest.raises(ValueError):check(candidate,row,**changes)


@pytest.mark.parametrize('changes',[
    dict(version=1),dict(source_format='CSV'),dict(source_checksum='0'*64),
    dict(actual_count=0),dict(result_actual_checksum='0'*64),dict(workflow_completed=False),
])
def test_mutated_excel_proof_rejected_even_with_recomputed_checksum(changes):
    candidate,row=fixture()
    row['evidence'].update(changes);row['checksum']=digest(row['evidence'])
    with pytest.raises(ValueError):check(candidate,row)


def test_csv_proof_cannot_substitute_for_excel():
    candidate,row=proof_fixture()
    with pytest.raises(ValueError):check(candidate,row)
