from jobs import run_perf_if_files as job
from pathlib import Path


def test_run_perf_job_triggers_when_temp_files_exist(monkeypatch):
    called = {"run": 0}
    monkeypatch.setattr(job, "TEMP_PERF_DIR", Path("/tmp/perf"))
    monkeypatch.setattr(job.glob, "glob", lambda pattern: ["/tmp/perf/a.csv"])
    monkeypatch.setattr(job, "acquire_missing_performance", lambda: called.__setitem__("run", called["run"] + 1))

    job.main()
    assert called["run"] == 1


def test_run_perf_job_skips_when_no_temp_files(monkeypatch):
    called = {"run": 0}
    monkeypatch.setattr(job, "TEMP_PERF_DIR", Path("/tmp/perf"))
    monkeypatch.setattr(job.glob, "glob", lambda pattern: [])
    monkeypatch.setattr(job, "acquire_missing_performance", lambda: called.__setitem__("run", called["run"] + 1))

    job.main()
    assert called["run"] == 0
