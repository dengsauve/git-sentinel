from __future__ import annotations

from pathlib import Path

import pytest

from git_sentinel.config import ConfigError, load_config


def test_load_config_merges_defaults_into_repository(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
defaults:
  remote: origin
  branch: main
  interval_seconds: 60
  commit:
    enabled: true
    message: "default commit"
    add: ["."]
repositories:
  - name: repo-a
    path: ~/repo-a
    push: true
""",
        encoding="utf-8",
    )

    config = load_config(config_path)

    repository = config.repositories[0]
    assert repository.remote == "origin"
    assert repository.branch == "main"
    assert repository.interval_seconds == 60
    assert repository.push is True
    assert repository.commit.enabled is True
    assert repository.commit.message == "default commit"
    assert repository.commit.add == ["."]
    assert repository.path == Path("~/repo-a").expanduser()


def test_load_config_rejects_duplicate_repository_names(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
repositories:
  - name: app
    path: /tmp/app1
    commit:
      enabled: false
  - name: app
    path: /tmp/app2
    commit:
      enabled: false
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="repository names must be unique"):
        load_config(config_path)


def test_load_config_requires_explicit_commit_for_push_enabled_repo(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
repositories:
  - name: app
    path: /tmp/app
    push: true
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="push-enabled repositories require"):
        load_config(config_path)
