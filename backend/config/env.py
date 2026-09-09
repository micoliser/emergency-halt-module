"""Tiny env readers so settings stay declarative."""

import os

TRUTHY = {"1", "true", "yes", "on"}
FALSY = {"0", "false", "no", "off", ""}


def env_str(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip()


def env_bool(name: str, default: bool = False) -> bool:
    raw = env_str(name, "").lower()
    if raw in TRUTHY:
        return True
    if raw in FALSY:
        return default if raw == "" else False
    return default


def env_int(name: str, default: int) -> int:
    raw = env_str(name, "")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    raw = env_str(name, "")
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def env_csv(name: str, default: list[str]) -> list[str]:
    raw = env_str(name, "")
    if not raw:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]
