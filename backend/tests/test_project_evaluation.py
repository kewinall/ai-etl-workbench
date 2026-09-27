from contextlib import contextmanager
from app.project_evaluation import read


class Repo:
    def __init__(self, rows): self.rows=rows
    @contextmanager
    def conn(self): yield self
    def execute(self, sql, params):
        assert params==('project-a',)
        assert 'WHERE t.project_id=%s' in sql
        assert 'c.project_id=t.project_id' in sql
        assert 'LEFT JOIN platform.task_run' in sql
        return self
    def fetchall(self): return self.rows


def test_preserves_failed_cancelled_and_release_without_claiming_improvement():
    rows=[{'state':'FAILED'},{'state':'CANCELLED'},{'state':'NEEDS_REVIEW','historical_release_count':1}]
    result=read(Repo(rows),'project-a')
    assert result['cases']==rows
    assert result['comparison_ready'] is False
    assert all(result[key] is None for key in ('human_baseline','improvement_rate','cost'))


def test_empty_inventory_does_not_claim_success():
    result=read(Repo([]),'project-a')
    assert result['cases']==[]
    assert result['comparison_ready'] is False
