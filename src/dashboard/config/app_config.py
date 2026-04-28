from __future__ import annotations

import copy
import errno
import os
import logging
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict

import yaml

log = logging.getLogger(__name__)

DEFAULT_APP_CONFIG: Dict[str, Any] = {
    "paths": {
        "performance_csv": "data/performance/Performance_sum.csv",
        "journal_live_csv": "data/performance/journal_live.csv",
        "journal_adjustments_csv": "data/performance/journal_adjustments.csv",
        "journal_matches_csv": "data/performance/journal_matches.csv",
        "taxonomy_csv": "data/metadata/taxonomy.csv",
        "contract_specs_csv": "data/metadata/contract_specs.csv",
        "day_plan_csv": "data/performance/day_plan.csv",
        "cashflow_csv": "data/portfolio/cashflow.csv",
        "trade_sum_csv": "data/portfolio/trade_sum.csv",
        "audit_log_jsonl": "data/audit/change_audit.jsonl",
    },
    "ui": {
        "timeframes": ["5m", "15m", "30m", "1h", "4h", "1d", "1w"],
        "playback_speeds": [15, 30, 45, 60],
    },
    "live_journal": {
        "daily_max_trade": 5,
        "daily_max_loss": 500.0,
    },
    "data_fetch": {
        "rate_limit_cooldown_minutes": 60,
        "manual_max_retries": 3,
        "manual_retry_delay_seconds": 10,
    },
    "analysis": {
        "initial_net_liq": 10000.0,
        "risk_free_rate": 0.02,
        "portfolio_start_date": "2025-11-01",
        "timezone": "US/Central",
        "include_unmatched_default": False,
        "session": {
            "start": "08:30",
            "end": "15:10",
            "phase_windows": {
                "open_start": "08:30",
                "open_end": "10:00",
                "middle_end": "14:00",
                "end_end": "15:10",
            },
        },
        "rule_compliance": {
            "max_trades_per_day": 8,
            "max_consecutive_losses": 3,
            "max_daily_loss": 500.0,
            "big_loss_threshold": 200.0,
            "max_trades_after_big_loss": 2,
        },
    },
    "symbols": {
        "default_performance_file": "data/performance/Performance_sum.csv",
    },
    "tagging": {
        "strict_mode": True,
    },
}


def _resolve_project_root() -> Path:
    env_root = os.environ.get("PROJECT_ROOT")
    if env_root:
        p = Path(env_root).resolve()
        if p.exists():
            return p
    here = Path(__file__).resolve()
    for parent in [*here.parents]:
        if (parent / "src" / "dashboard").exists():
            return parent
    return Path.cwd()


_CONFIG_LOCK = threading.RLock()
_CONFIG_CACHE: Dict[str, Any] | None = None
_CONFIG_CACHE_MTIME_NS: int | None = None
_CONFIG_CACHE_PATH: Path | None = None


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def app_config_path() -> Path:
    raw = os.environ.get("APP_CONFIG_PATH", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (_resolve_project_root() / "config" / "app_config.yaml").resolve()


def get_app_config() -> Dict[str, Any]:
    global _CONFIG_CACHE, _CONFIG_CACHE_MTIME_NS, _CONFIG_CACHE_PATH
    p = app_config_path()
    try:
        mtime_ns = p.stat().st_mtime_ns if p.exists() else None
    except OSError:
        mtime_ns = None
    with _CONFIG_LOCK:
        if _CONFIG_CACHE is not None and _CONFIG_CACHE_PATH == p and _CONFIG_CACHE_MTIME_NS == mtime_ns:
            return copy.deepcopy(_CONFIG_CACHE)

        cfg = copy.deepcopy(DEFAULT_APP_CONFIG)
        if p.exists():
            try:
                loaded = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                if isinstance(loaded, dict):
                    cfg = _deep_merge(cfg, loaded)
            except (OSError, yaml.YAMLError, TypeError, ValueError) as exc:
                log.warning("Failed to load app config from %s, using defaults: %s", p, exc)
        _CONFIG_CACHE = cfg
        _CONFIG_CACHE_MTIME_NS = mtime_ns
        _CONFIG_CACHE_PATH = p
        return copy.deepcopy(cfg)


def clear_app_config_cache() -> None:
    global _CONFIG_CACHE, _CONFIG_CACHE_MTIME_NS, _CONFIG_CACHE_PATH
    with _CONFIG_LOCK:
        _CONFIG_CACHE = None
        _CONFIG_CACHE_MTIME_NS = None
        _CONFIG_CACHE_PATH = None


def raw_app_config() -> Dict[str, Any]:
    p = app_config_path()
    if not p.exists():
        return {}
    loaded = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError("app config YAML must contain an object at the top level")
    return loaded


def write_app_config(raw_config: Dict[str, Any]) -> None:
    if not isinstance(raw_config, dict):
        raise ValueError("app config must be an object")
    p = app_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.safe_dump(raw_config, sort_keys=False, allow_unicode=False)
    with _CONFIG_LOCK:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{p.name}.", suffix=".tmp", dir=str(p.parent), text=True)
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            try:
                os.replace(tmp_path, p)
            except OSError as exc:
                if exc.errno != errno.EBUSY:
                    raise
                # Docker single-file bind mounts can reject atomic replace with
                # EBUSY. In that case keep the mount identity and update the
                # file contents in place.
                p.write_text(content, encoding="utf-8")
            clear_app_config_cache()
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass


def resolve_path(path_value: str, base_dir: Path) -> Path:
    p = Path(path_value)
    return p if p.is_absolute() else (base_dir / p)


def public_app_config() -> Dict[str, Any]:
    return {
        "config_path": str(app_config_path()),
        "config": get_app_config(),
    }
