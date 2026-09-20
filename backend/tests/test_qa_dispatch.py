from unittest.mock import Mock
import pytest
from app.qa_dispatch import dispatch_qa


def test_requires_separate_model_consent(monkeypatch):
    monkeypatch.setenv('WORKBENCH_QA_DISPATCH_ENABLED','true')
    with pytest.raises(ValueError,match='QA_MODEL_CALL_CONSENT_REQUIRED'):
        dispatch_qa(None,None,'task','run','comparison','checksum')


def test_default_disabled_before_any_database_or_provider_call(monkeypatch):
    monkeypatch.delenv('WORKBENCH_QA_DISPATCH_ENABLED',raising=False)
    provider=Mock()
    with pytest.raises(ValueError,match='QA_DISPATCH_DISABLED'):
        dispatch_qa(None,None,'task','run','comparison','checksum',authorize_model_call=True,completion=provider)
    provider.assert_not_called()
