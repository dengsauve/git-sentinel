from __future__ import annotations

from pathlib import Path
from threading import Event

import pytest

from git_sentinel.models import (
    AppConfig,
    CommitSettings,
    HookFailurePolicy,
    RepositoryConfig,
)
from git_sentinel.service import SentinelService


def test_run_once_filters_to_named_repository(initialized_repo: Path) -> None:
    repo_a = RepositoryConfig(
        name="repo-a",
        path=initialized_repo,
        interval_seconds=60,
        pull=False,
        push=False,
        commit=CommitSettings(enabled=False),
    )
    repo_b = RepositoryConfig(
        name="repo-b",
        path=initialized_repo,
        interval_seconds=60,
        pull=False,
        push=False,
        commit=CommitSettings(enabled=False),
    )
    service = SentinelService(
        AppConfig(repositories=[repo_a, repo_b]), shutdown_event=Event()
    )

    results = service.run_once(repository_name="repo-b")

    assert [result.repository for result in results] == ["repo-b"]


def test_run_repository_cycle_fails_on_hook_policy_fail(
    remote_with_clone: tuple[Path, Path],
) -> None:
    _, clone = remote_with_clone
    hook_script = clone / "hook.py"
    hook_script.write_text("raise SystemExit(2)\n", encoding="utf-8")
    repository = RepositoryConfig(
        name="repo",
        path=clone,
        interval_seconds=60,
        pull=False,
        push=True,
        commit=CommitSettings(enabled=True, message="chore: sync", add=["."]),
        after_push=[["python3", str(hook_script)]],
        hook_failure_policy=HookFailurePolicy.FAIL,
    )
    (clone / "file.txt").write_text("changed\n", encoding="utf-8")

    service = SentinelService(
        AppConfig(repositories=[repository]),
        shutdown_event=Event(),
    )
    result = service.run_repository_cycle(repository)

    assert result.repository == "repo"
    assert result.committed is True
    assert result.pushed is True
    assert result.hook_results == []


def test_run_once_raises_for_unknown_repository(initialized_repo: Path) -> None:
    repository = RepositoryConfig(
        name="repo",
        path=initialized_repo,
        interval_seconds=60,
        pull=False,
        push=False,
        commit=CommitSettings(enabled=False),
    )
    service = SentinelService(
        AppConfig(repositories=[repository]),
        shutdown_event=Event(),
    )

    with pytest.raises(ValueError, match="repository not found"):
        service.run_once(repository_name="missing")
