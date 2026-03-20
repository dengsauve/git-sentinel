"""YAML configuration loading and validation."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from git_sentinel.models import AppConfig, RawConfig, RepositoryConfig


class ConfigError(ValueError):
    """Raised when the configuration file is invalid."""


def load_config(config_path: Path) -> AppConfig:
    """Load, merge, and validate application configuration."""

    if not config_path.exists():
        raise ConfigError(f"config file does not exist: {config_path}")
    if not config_path.is_file():
        raise ConfigError(f"config path is not a file: {config_path}")

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"failed to parse YAML from {config_path}: {exc}") from exc

    if data is None:
        raise ConfigError(f"config file is empty: {config_path}")
    if not isinstance(data, dict):
        raise ConfigError("config root must be a mapping")

    try:
        raw_config = RawConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(_format_validation_error(exc)) from exc

    repositories: list[RepositoryConfig] = []
    defaults = raw_config.defaults.model_dump(mode="python")
    for index, repository_data in enumerate(raw_config.repositories):
        merged = _merge_repository(defaults, repository_data)
        try:
            repository = RepositoryConfig.model_validate(merged)
        except ValidationError as exc:
            repository_name = merged.get("name", f"index {index}")
            raise ConfigError(
                _format_repository_error(repository_name=repository_name, error=exc)
            ) from exc
        repositories.append(repository)

    try:
        return AppConfig(repositories=repositories)
    except ValidationError as exc:
        raise ConfigError(_format_validation_error(exc)) from exc


def _merge_repository(
    defaults: dict[str, Any], repository_data: dict[str, object]
) -> dict[str, object]:
    merged = dict(defaults)
    for key, value in repository_data.items():
        existing = merged.get(key)
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            merged[key] = {**dict(existing), **dict(value)}
            continue
        merged[key] = value
    return merged


def _format_validation_error(error: ValidationError) -> str:
    lines = ["configuration validation failed:"]
    for entry in error.errors():
        location = ".".join(str(part) for part in entry["loc"])
        lines.append(f"- {location}: {entry['msg']}")
    return "\n".join(lines)


def _format_repository_error(repository_name: object, error: ValidationError) -> str:
    lines = [f"repository '{repository_name}' validation failed:"]
    for entry in error.errors():
        location = ".".join(str(part) for part in entry["loc"])
        lines.append(f"- {location}: {entry['msg']}")
    return "\n".join(lines)
