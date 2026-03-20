"""Explicit Git command helpers."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from time import monotonic

from git_sentinel.models import RepositoryConfig


class GitOperationError(RuntimeError):
    """Raised when a Git command fails or repository state is invalid."""


@dataclass(frozen=True)
class CommandResult:
    """Normalized subprocess result used by hooks and Git operations."""

    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int


def verify_repository_path(path: Path) -> None:
    """Ensure a configured path is an existing Git repository."""

    if not path.exists():
        raise GitOperationError(f"repository path does not exist: {path}")
    if not path.is_dir():
        raise GitOperationError(f"repository path is not a directory: {path}")
    if not (path / ".git").exists():
        raise GitOperationError(f"path is not a Git repository: {path}")


def run_git_command(path: Path, args: list[str]) -> CommandResult:
    """Run a Git command in a repository and capture execution details."""

    command = ["git", *args]
    start = monotonic()
    completed = subprocess.run(
        command,
        cwd=path,
        capture_output=True,
        text=True,
        check=False,
    )
    duration_ms = int((monotonic() - start) * 1000)
    result = CommandResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration_ms=duration_ms,
    )
    if completed.returncode != 0:
        raise GitOperationError(_format_command_failure(result))
    return result


def get_current_branch(path: Path) -> str:
    """Return the current local branch name."""

    result = run_git_command(path, ["rev-parse", "--abbrev-ref", "HEAD"])
    branch = result.stdout.strip()
    if branch == "HEAD":
        raise GitOperationError("detached HEAD is not supported")
    return branch


def ensure_expected_branch(path: Path, expected_branch: str) -> None:
    """Validate that the repository is on the configured branch."""

    current_branch = get_current_branch(path)
    if current_branch != expected_branch:
        raise GitOperationError(
            "repository branch mismatch: "
            f"expected {expected_branch}, found {current_branch}"
        )


def has_tracked_or_untracked_changes(path: Path) -> bool:
    """Return True when the working tree contains changes."""

    result = run_git_command(path, ["status", "--porcelain"])
    return bool(result.stdout.strip())


def pull_repository(config: RepositoryConfig) -> CommandResult:
    """Fetch and fast-forward the configured repository branch."""

    verify_repository_path(config.path)
    ensure_expected_branch(config.path, config.branch)
    return run_git_command(
        config.path,
        ["pull", "--ff-only", config.remote, config.branch],
    )


def stage_changes(path: Path, paths: list[str]) -> CommandResult:
    """Stage configured paths before commit."""

    return run_git_command(path, ["add", "--", *paths])


def create_commit(path: Path, message: str) -> CommandResult:
    """Create a commit for staged changes."""

    return run_git_command(path, ["commit", "-m", message])


def push_repository(config: RepositoryConfig) -> CommandResult:
    """Push the configured branch to the configured remote."""

    verify_repository_path(config.path)
    ensure_expected_branch(config.path, config.branch)
    return run_git_command(config.path, ["push", config.remote, config.branch])


def commit_and_push_if_needed(
    config: RepositoryConfig,
) -> tuple[CommandResult | None, CommandResult | None]:
    """Create a commit and push when the repository has local changes."""

    verify_repository_path(config.path)
    ensure_expected_branch(config.path, config.branch)

    if not config.push:
        return None, None

    if not has_tracked_or_untracked_changes(config.path):
        return None, None

    if not config.commit.enabled or config.commit.message is None:
        raise GitOperationError(
            f"repository {config.name} has changes but commit settings are not enabled"
        )

    stage_changes(config.path, config.commit.add)
    commit_result = create_commit(config.path, config.commit.message)
    push_result = push_repository(config)
    return commit_result, push_result


def _format_command_failure(result: CommandResult) -> str:
    command = " ".join(result.command)
    return (
        f"command failed: {command}; returncode={result.returncode}; "
        f"stdout={result.stdout.strip()!r}; stderr={result.stderr.strip()!r}"
    )
