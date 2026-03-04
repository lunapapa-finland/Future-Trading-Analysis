from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_JOB_PATH = Path(__file__).resolve().parents[1] / "jobs" / "run_perf_if_files.py"
_SPEC = spec_from_file_location("run_perf_if_files", _JOB_PATH)
assert _SPEC is not None and _SPEC.loader is not None
job = module_from_spec(_SPEC)
_SPEC.loader.exec_module(job)


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
