from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def git_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Test User")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Test User")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.com")


@pytest.fixture
def initialized_repo(tmp_path: Path, git_env: None) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "main"], cwd=repo)
    (repo / "README.md").write_text("initial\n", encoding="utf-8")
    run(["git", "add", "README.md"], cwd=repo)
    run(["git", "commit", "-m", "initial commit"], cwd=repo)
    return repo


@pytest.fixture
def remote_with_clone(tmp_path: Path, git_env: None) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    working = tmp_path / "seed"
    clone = tmp_path / "clone"

    run(["git", "init", "--bare", str(remote)], cwd=tmp_path)
    working.mkdir()
    run(["git", "init", "-b", "main"], cwd=working)
    (working / "README.md").write_text("initial\n", encoding="utf-8")
    run(["git", "add", "README.md"], cwd=working)
    run(["git", "commit", "-m", "initial"], cwd=working)
    run(["git", "remote", "add", "origin", str(remote)], cwd=working)
    run(["git", "push", "-u", "origin", "main"], cwd=working)
    run(["git", "clone", str(remote), str(clone)], cwd=tmp_path)
    return remote, clone
