from datetime import datetime
from pathlib import Path

from app import task_uploads


def test_csv_upload_profiles_fields_and_retention(tmp_path, monkeypatch):
    monkeypatch.setattr(task_uploads, "UPLOAD_ROOT", tmp_path / "uploads")
    result = task_uploads.save_and_profile(
        "codes.csv", b"code,quantity,price\nA,2,10.5\nB,3,20.0\n", retention_days=7
    )
    assert result["source_type"] == "CSV"
    assert result["fields"] == [
        {"name": "code", "type": "VARCHAR(32)"},
        {"name": "quantity", "type": "BIGINT"},
        {"name": "price", "type": "DECIMAL(18,4)"},
    ]
    assert Path(result["path"]).is_file()
    assert (datetime.fromisoformat(result["expires_at"]) - datetime.now().astimezone()).days in (6, 7)


def test_upload_rejects_unsupported_extension(tmp_path, monkeypatch):
    monkeypatch.setattr(task_uploads, "UPLOAD_ROOT", tmp_path / "uploads")
    try:
        task_uploads.save_and_profile("data.xls", b"legacy")
        assert False, "expected unsupported extension"
    except ValueError as exc:
        assert "CSV" in str(exc) and "XLSX" in str(exc)
