from __future__ import annotations

import copy
import math
import re
from dataclasses import dataclass
from typing import Any, Callable, Literal

import yaml

from dashboard.config.app_config import (
    app_config_path,
    clear_app_config_cache,
    get_app_config,
    raw_app_config,
    write_app_config,
)

FieldType = Literal["number", "integer", "boolean", "string_list", "integer_list", "date"]


@dataclass(frozen=True)
class RuntimeField:
    key: str
    label: str
    section: str
    type: FieldType
    min: float | None = None
    max: float | None = None


RUNTIME_FIELDS: tuple[RuntimeField, ...] = (
    RuntimeField("ui.timeframes", "Timeframes", "UI", "string_list"),
    RuntimeField("ui.playback_speeds", "Playback speeds", "UI", "integer_list", min=1),
    RuntimeField("analysis.initial_net_liq", "Initial net liquidation", "Analysis Defaults", "number", min=0),
    RuntimeField("analysis.risk_free_rate", "Risk-free rate", "Analysis Defaults", "number", min=0, max=1),
    RuntimeField("analysis.portfolio_start_date", "Portfolio start date", "Analysis Defaults", "date"),
    RuntimeField("analysis.include_unmatched_default", "Include unmatched trades", "Analysis Defaults", "boolean"),
    RuntimeField("analysis.rule_compliance.max_trades_per_day", "Max trades per day", "Rule Compliance", "integer", min=1),
    RuntimeField("analysis.rule_compliance.max_consecutive_losses", "Max consecutive losses", "Rule Compliance", "integer", min=1),
    RuntimeField("analysis.rule_compliance.max_daily_loss", "Max daily loss", "Rule Compliance", "number", min=0),
    RuntimeField("analysis.rule_compliance.big_loss_threshold", "Big loss threshold", "Rule Compliance", "number", min=0),
    RuntimeField("analysis.rule_compliance.max_trades_after_big_loss", "Max trades after big loss", "Rule Compliance", "integer", min=0),
    RuntimeField("live_journal.daily_max_trade", "Daily max trades", "Live Journal", "integer", min=1),
    RuntimeField("live_journal.daily_max_loss", "Daily max loss", "Live Journal", "number", min=0),
    RuntimeField("data_fetch.rate_limit_cooldown_minutes", "Rate-limit cooldown", "Data Fetch", "integer", min=1),
    RuntimeField("data_fetch.manual_max_retries", "Manual max retries", "Data Fetch", "integer", min=1),
    RuntimeField("data_fetch.manual_retry_delay_seconds", "Manual retry delay", "Data Fetch", "integer", min=0),
    RuntimeField("tagging.strict_mode", "Strict tag validation", "Tagging", "boolean"),
)

FIELD_MAP = {field.key: field for field in RUNTIME_FIELDS}


def _get_nested(data: dict[str, Any], key: str) -> Any:
    current: Any = data
    for part in key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _set_nested(data: dict[str, Any], key: str, value: Any) -> None:
    current = data
    parts = key.split(".")
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[parts[-1]] = value


def _yaml_comment_descriptions() -> dict[str, str]:
    path = app_config_path()
    if not path.exists():
        return {}
    descriptions: dict[str, str] = {}
    stack: list[tuple[int, str]] = []
    pending: dict[int, list[str]] = {}
    key_re = re.compile(r"^(\s*)([A-Za-z0-9_]+)\s*:(.*)$")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    for line in lines:
        stripped = line.strip()
        if not stripped:
            pending.clear()
            continue
        indent = len(line) - len(line.lstrip(" "))
        if stripped.startswith("#"):
            pending.setdefault(indent, []).append(stripped.lstrip("#").strip())
            continue
        match = key_re.match(line)
        if not match:
            pending.pop(indent, None)
            continue
        key = match.group(2)
        rest = match.group(3).strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        path_key = ".".join([part for _, part in stack] + [key])
        comments = pending.pop(indent, [])
        if comments:
            descriptions[path_key] = " ".join(comments)
        if not rest:
            stack.append((indent, key))
    return descriptions


def _inline_yaml(value: Any) -> str:
    dumped = yaml.safe_dump(value, default_flow_style=True, sort_keys=False).strip()
    if dumped.endswith("\n..."):
        dumped = dumped[:-4].strip()
    if "\n" in dumped:
        dumped = dumped.splitlines()[0].strip()
    return dumped


def _write_runtime_config_preserving_comments(updates: dict[str, Any], fallback_raw: dict[str, Any]) -> None:
    path = app_config_path()
    if not path.exists():
        write_app_config(fallback_raw)
        return
    key_re = re.compile(r"^(\s*)([A-Za-z0-9_]+)(\s*:\s*)(.*)$")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        write_app_config(fallback_raw)
        return

    remaining = dict(updates)
    stack: list[tuple[int, str]] = []
    out: list[str] = []
    for line in lines:
        match = key_re.match(line)
        if not match:
            out.append(line)
            continue
        indent = len(match.group(1))
        key = match.group(2)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        path_key = ".".join([part for _, part in stack] + [key])
        if path_key in remaining:
            out.append(f"{match.group(1)}{key}: {_inline_yaml(remaining.pop(path_key))}")
        else:
            out.append(line)
        if match.group(4).strip() == "":
            stack.append((indent, key))

    if remaining:
        write_app_config(fallback_raw)
        return
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    clear_app_config_cache()


def _finite_number(value: Any, field: RuntimeField) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field.key} must be a number")
    try:
        out = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field.key} must be a number")
    if not math.isfinite(out):
        raise ValueError(f"{field.key} must be finite")
    if field.min is not None and out < field.min:
        raise ValueError(f"{field.key} must be >= {field.min}")
    if field.max is not None and out > field.max:
        raise ValueError(f"{field.key} must be <= {field.max}")
    return out


def _integer(value: Any, field: RuntimeField) -> int:
    out = _finite_number(value, field)
    if int(out) != out:
        raise ValueError(f"{field.key} must be an integer")
    return int(out)


def _boolean(value: Any, field: RuntimeField) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"{field.key} must be true or false")


def _string_list(value: Any, field: RuntimeField) -> list[str]:
    if isinstance(value, str):
        raw_values = [part.strip() for part in value.replace("\n", ",").split(",")]
    elif isinstance(value, list):
        raw_values = [str(part).strip() for part in value]
    else:
        raise ValueError(f"{field.key} must be a list")
    values = [item for item in raw_values if item]
    if not values:
        raise ValueError(f"{field.key} must include at least one value")
    return values


def _integer_list(value: Any, field: RuntimeField) -> list[int]:
    if isinstance(value, str):
        raw_values: list[Any] = [part.strip() for part in value.replace("\n", ",").split(",")]
    elif isinstance(value, list):
        raw_values = value
    else:
        raise ValueError(f"{field.key} must be a list")
    values = [_integer(item, field) for item in raw_values if str(item).strip()]
    if not values:
        raise ValueError(f"{field.key} must include at least one value")
    return values


def _date(value: Any, field: RuntimeField) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field.key} is required")
    import datetime as _dt

    try:
        _dt.date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"{field.key} must be YYYY-MM-DD")
    return text


VALIDATORS: dict[FieldType, Callable[[Any, RuntimeField], Any]] = {
    "number": _finite_number,
    "integer": _integer,
    "boolean": _boolean,
    "string_list": _string_list,
    "integer_list": _integer_list,
    "date": _date,
}


def runtime_config_payload() -> dict[str, Any]:
    effective = get_app_config()
    descriptions = _yaml_comment_descriptions()
    return {
        "config_path": str(app_config_path()),
        "apply_mode": "live",
        "fields": [
            {
                "key": field.key,
                "label": field.label,
                "section": field.section,
                "type": field.type,
                "description": descriptions.get(field.key, ""),
                "min": field.min,
                "max": field.max,
                "value": _get_nested(effective, field.key),
            }
            for field in RUNTIME_FIELDS
        ],
    }


def update_runtime_config(updates: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(updates, dict):
        raise ValueError("updates must be an object")
    raw = raw_app_config()
    next_raw = copy.deepcopy(raw)
    normalized_updates: dict[str, Any] = {}
    for key, value in updates.items():
        field = FIELD_MAP.get(key)
        if field is None:
            raise ValueError(f"{key} is not editable at runtime")
        normalized = VALIDATORS[field.type](value, field)
        normalized_updates[key] = normalized
        _set_nested(next_raw, key, normalized)
    _write_runtime_config_preserving_comments(normalized_updates, next_raw)
    return runtime_config_payload()
