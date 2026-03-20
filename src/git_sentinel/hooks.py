"""Configured post-operation hook execution."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from time import monotonic


class HookExecutionError(RuntimeError):
    """Raised when hook execution should fail the repository cycle."""


@dataclass(frozen=True)
class HookResult:
    """Captured result for a configured hook command."""

    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0


def run_hooks(commands: list[list[str]], cwd: Path) -> list[HookResult]:
    """Run hooks sequentially with the repository as working directory."""

    results: list[HookResult] = []
    for command in commands:
        start = monotonic()
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        duration_ms = int((monotonic() - start) * 1000)
        results.append(
            HookResult(
                command=list(command),
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                duration_ms=duration_ms,
            )
        )
    return results
