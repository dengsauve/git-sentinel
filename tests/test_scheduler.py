from __future__ import annotations

from pathlib import Path

from git_sentinel.models import CommitSettings, RepositoryConfig
from git_sentinel.scheduler import Scheduler


def make_repository(name: str, interval_seconds: int = 30) -> RepositoryConfig:
    return RepositoryConfig(
        name=name,
        path=Path("/tmp") / name,
        interval_seconds=interval_seconds,
        pull=True,
        push=False,
        commit=CommitSettings(enabled=False),
    )


def test_scheduler_returns_due_repositories_and_prevents_overlap() -> None:
    scheduler = Scheduler([make_repository("alpha", interval_seconds=10)])

    due = scheduler.due_repositories(now=100.0)
    assert [repo.name for repo in due] == ["alpha"]

    scheduler.mark_started("alpha", now=100.0)
    assert scheduler.due_repositories(now=100.0) == []

    scheduler.mark_finished("alpha", now=101.0)
    assert scheduler.due_repositories(now=105.0) == []
    assert [repo.name for repo in scheduler.due_repositories(now=111.0)] == ["alpha"]


def test_scheduler_reports_seconds_until_next_run() -> None:
    scheduler = Scheduler([make_repository("alpha", interval_seconds=20)])
    scheduler.mark_started("alpha", now=50.0)
    scheduler.mark_finished("alpha", now=55.0)

    assert scheduler.seconds_until_next_run(now=60.0) == 15.0
