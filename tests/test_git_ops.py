from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from git_sentinel.git_ops import (
    GitOperationError,
    commit_and_push_if_needed,
    pull_repository,
    push_repository,
)
from git_sentinel.models import CommitSettings, RepositoryConfig


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def make_repo_config(
    path: Path, *, pull: bool = True, push: bool = False, remote: str = "origin"
) -> RepositoryConfig:
    return RepositoryConfig(
        name=path.name,
        path=path,
        remote=remote,
        branch="main",
        interval_seconds=60,
        pull=pull,
        push=push,
        commit=CommitSettings(
            enabled=push,
            message="chore: sync",
            add=["."] if push else [],
        ),
    )


def test_pull_repository_fetches_remote_changes(
    remote_with_clone: tuple[Path, Path], git_env: None, tmp_path: Path
) -> None:
    remote, clone = remote_with_clone
    upstream = tmp_path / "upstream"
    run(["git", "clone", str(remote), str(upstream)], cwd=tmp_path)
    (upstream / "README.md").write_text("updated\n", encoding="utf-8")
    run(["git", "add", "README.md"], cwd=upstream)
    run(["git", "commit", "-m", "update"], cwd=upstream)
    run(["git", "push", "origin", "main"], cwd=upstream)

    result = pull_repository(make_repo_config(clone))

    assert result.returncode == 0
    assert (clone / "README.md").read_text(encoding="utf-8") == "updated\n"


def test_commit_and_push_if_needed_creates_commit_and_pushes(
    remote_with_clone: tuple[Path, Path],
) -> None:
    remote, clone = remote_with_clone
    (clone / "generated.txt").write_text("payload\n", encoding="utf-8")

    commit_result, push_result = commit_and_push_if_needed(
        make_repo_config(clone, push=True)
    )

    assert commit_result is not None
    assert push_result is not None

    verify = Path(str(remote) + ".verify")
    run(["git", "clone", str(remote), str(verify)], cwd=remote.parent)
    assert (verify / "generated.txt").read_text(encoding="utf-8") == "payload\n"


def test_push_repository_rejects_wrong_branch(initialized_repo: Path) -> None:
    config = RepositoryConfig(
        name="repo",
        path=initialized_repo,
        remote="origin",
        branch="develop",
        interval_seconds=60,
        pull=False,
        push=True,
        commit=CommitSettings(enabled=True, message="chore: sync", add=["."]),
    )

    with pytest.raises(GitOperationError, match="branch mismatch"):
        push_repository(config)
