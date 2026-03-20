from __future__ import annotations

from pathlib import Path

from git_sentinel.hooks import run_hooks


def test_run_hooks_captures_success_and_failure(tmp_path: Path) -> None:
    hook_script = tmp_path / "hook.py"
    hook_script.write_text(
        """
import sys
print("stdout line")
print("stderr line", file=sys.stderr)
raise SystemExit(3)
""",
        encoding="utf-8",
    )

    results = run_hooks([["python3", str(hook_script)]], cwd=tmp_path)

    assert len(results) == 1
    result = results[0]
    assert result.returncode == 3
    assert result.succeeded is False
    assert "stdout line" in result.stdout
    assert "stderr line" in result.stderr
    assert result.duration_ms >= 0
