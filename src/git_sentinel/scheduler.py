"""Cadence tracking and non-overlapping dispatch decisions."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from git_sentinel.models import RepositoryConfig


@dataclass
class RepositoryScheduleState:
    """Mutable schedule state for a single repository."""

    config: RepositoryConfig
    last_run_monotonic: float | None = None
    next_run_monotonic: float = 0.0
    running: bool = False


class Scheduler:
    """Simple single-process scheduler with per-repository overlap prevention."""

    def __init__(self, repositories: list[RepositoryConfig]) -> None:
        self._states = {
            repository.name: RepositoryScheduleState(config=repository)
            for repository in repositories
        }

    @property
    def states(self) -> dict[str, RepositoryScheduleState]:
        return self._states

    def due_repositories(self, now: float | None = None) -> list[RepositoryConfig]:
        """Return repositories ready for execution and not currently running."""

        current = monotonic() if now is None else now
        due: list[RepositoryConfig] = []
        for state in self._states.values():
            if state.running:
                continue
            if current >= state.next_run_monotonic:
                due.append(state.config)
        return due

    def mark_started(self, repository_name: str, now: float | None = None) -> None:
        """Mark a repository cycle as started."""

        state = self._states[repository_name]
        state.running = True
        state.last_run_monotonic = monotonic() if now is None else now

    def mark_finished(self, repository_name: str, now: float | None = None) -> None:
        """Mark a repository cycle as finished and schedule the next run."""

        current = monotonic() if now is None else now
        state = self._states[repository_name]
        state.running = False
        state.next_run_monotonic = current + state.config.interval_seconds

    def seconds_until_next_run(self, now: float | None = None) -> float:
        """Return the sleep time until the next repository is due."""

        current = monotonic() if now is None else now
        next_run = min(state.next_run_monotonic for state in self._states.values())
        return max(0.0, next_run - current)
