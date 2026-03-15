from pathlib import Path

import dashboard.services.utils.data_init as data_init


def test_ensure_required_csvs_creates_headers_for_missing_files(tmp_path, monkeypatch):
    schemas = {
        str(tmp_path / "a.csv"): ["c1", "c2"],
        str(tmp_path / "b.csv"): ["x"],
    }
    monkeypatch.setattr(data_init, "CSV_SCHEMAS", schemas)

    created = data_init.ensure_required_csvs()
    assert len(created) == 2

    a = Path(str(tmp_path / "a.csv")).read_text(encoding="utf-8").strip()
    b = Path(str(tmp_path / "b.csv")).read_text(encoding="utf-8").strip()
    assert a == "c1,c2"
    assert b == "x"
