"""Service loop and repository cycle orchestration."""

from __future__ import annotations

import logging
import signal
from dataclasses import dataclass
from threading import Event
from time import monotonic

from git_sentinel.git_ops import (
    CommandResult,
    GitOperationError,
    commit_and_push_if_needed,
    pull_repository,
)
from git_sentinel.hooks import HookResult, run_hooks
from git_sentinel.logging_config import get_logger
from git_sentinel.models import AppConfig, HookFailurePolicy, RepositoryConfig
from git_sentinel.scheduler import Scheduler


@dataclass(frozen=True)
class RepositoryCycleResult:
    """Outcome of a single repository cycle."""

    repository: str
    pulled: bool
    committed: bool
    pushed: bool
    hook_results: list[HookResult]


class SentinelService:
    """Long-running service that manages configured repositories."""

    def __init__(self, config: AppConfig, shutdown_event: Event | None = None) -> None:
        self.config = config
        self.shutdown_event = shutdown_event or Event()
        self.scheduler = Scheduler(config.repositories)
        self.logger = get_logger(__name__)

    def install_signal_handlers(self) -> None:
        """Register signal handlers that request a graceful shutdown."""

        signal.signal(signal.SIGINT, self._handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)

    def run_forever(self) -> None:
        """Run the continuous service loop until shutdown is requested."""

        self.logger.info("service starting")
        while not self.shutdown_event.is_set():
            due_repositories = self.scheduler.due_repositories()
            if not due_repositories:
                sleep_seconds = min(1.0, self.scheduler.seconds_until_next_run())
                self.shutdown_event.wait(timeout=sleep_seconds)
                continue

            for repository in due_repositories:
                if self.shutdown_event.is_set():
                    break
                self.run_repository_cycle(repository)
        self.logger.info("service stopping")

    def run_once(
        self,
        repository_name: str | None = None,
    ) -> list[RepositoryCycleResult]:
        """Run a single cycle for one or all repositories."""

        repositories = self._select_repositories(repository_name)
        return [self.run_repository_cycle(repository) for repository in repositories]

    def run_repository_cycle(
        self,
        repository: RepositoryConfig,
    ) -> RepositoryCycleResult:
        """Run pull, commit/push, and hook operations for a single repository."""

        start = monotonic()
        self.scheduler.mark_started(repository.name)
        logger = get_logger(__name__)
        logger.info(
            "repository cycle starting",
            extra={"repository": repository.name, "operation": "cycle"},
        )

        pulled = False
        committed = False
        pushed = False
        hook_results: list[HookResult] = []

        try:
            if repository.pull:
                pull_result = pull_repository(repository)
                pulled = True
                self._log_command_result(repository.name, "pull", pull_result)
                hook_results.extend(
                    self._run_hook_group(
                        repository=repository,
                        operation="after_pull",
                        commands=repository.after_pull,
                    )
                )

            commit_result: CommandResult | None
            push_result: CommandResult | None
            commit_result, push_result = commit_and_push_if_needed(repository)
            if commit_result is not None:
                committed = True
                self._log_command_result(repository.name, "commit", commit_result)
            if push_result is not None:
                pushed = True
                self._log_command_result(repository.name, "push", push_result)
                hook_results.extend(
                    self._run_hook_group(
                        repository=repository,
                        operation="after_push",
                        commands=repository.after_push,
                    )
                )
        except (GitOperationError, RuntimeError) as exc:
            logger.exception(
                "repository cycle failed: %s",
                exc,
                extra={"repository": repository.name, "operation": "cycle"},
            )
        finally:
            duration_ms = int((monotonic() - start) * 1000)
            self.scheduler.mark_finished(repository.name)
            logger.info(
                (
                    "repository cycle finished duration_ms=%s "
                    "pulled=%s committed=%s pushed=%s"
                ),
                duration_ms,
                pulled,
                committed,
                pushed,
                extra={"repository": repository.name, "operation": "cycle"},
            )

        return RepositoryCycleResult(
            repository=repository.name,
            pulled=pulled,
            committed=committed,
            pushed=pushed,
            hook_results=hook_results,
        )

    def _run_hook_group(
        self, repository: RepositoryConfig, operation: str, commands: list[list[str]]
    ) -> list[HookResult]:
        if not commands:
            return []

        logger = get_logger(__name__)
        results = run_hooks(commands=commands, cwd=repository.path)
        for result in results:
            logger.info(
                "hook completed returncode=%s duration_ms=%s command=%s",
                result.returncode,
                result.duration_ms,
                result.command,
                extra={"repository": repository.name, "operation": operation},
            )
            if (
                not result.succeeded
                and repository.hook_failure_policy is HookFailurePolicy.FAIL
            ):
                raise RuntimeError(
                    f"hook failed for repository {repository.name}: "
                    f"{' '.join(result.command)}"
                )
        return results

    def _select_repositories(
        self,
        repository_name: str | None,
    ) -> list[RepositoryConfig]:
        if repository_name is None:
            return self.config.repositories

        matches = [
            repo for repo in self.config.repositories if repo.name == repository_name
        ]
        if not matches:
            raise ValueError(f"repository not found: {repository_name}")
        return matches

    def _handle_shutdown_signal(self, signum: int, _frame: object) -> None:
        logger = get_logger(__name__)
        signal_name = signal.Signals(signum).name
        logger.info("shutdown requested via %s", signal_name)
        self.shutdown_event.set()

    def _log_command_result(
        self, repository_name: str, operation: str, result: CommandResult
    ) -> None:
        logging.getLogger(__name__).info(
            "command succeeded returncode=%s duration_ms=%s command=%s",
            result.returncode,
            result.duration_ms,
            result.command,
            extra={"repository": repository_name, "operation": operation},
        )
