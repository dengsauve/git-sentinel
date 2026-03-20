# AGENTS.md

## Project Overview
`git-sentinel` is a long-running Python service that manages one or more Git repositories on a user-defined cadence. It should be safe to run continuously as a daemon-like process with minimal operator intervention.

The program reads repository definitions and behavior from a YAML configuration file. For each configured repository, it may:
- pull changes on a schedule
- optionally push local changes on a schedule or when conditions are met
- optionally run one or more commands after pull and/or push operations

The intended use case is "set and forget" automation for repositories that back dashboards, configs, generated artifacts, or other user-maintained state that changes over time.

## Primary Goals
- Build a reliable daemon-like Python program that continuously manages Git repositories from YAML configuration.
- Make repository behavior declarative and configuration-driven rather than hard-coded.
- Support both pull-only and push/pull repository workflows.
- Support post-operation hooks for commands that should run after pull or push.
- Prioritize safety, observability, and predictable behavior over cleverness.
- Keep the initial implementation simple, maintainable, and production-friendly.

## Product Expectations
The service should:
- load repository definitions from a YAML file
- validate configuration before starting work
- schedule repository actions on a cadence
- pull repositories safely and idempotently
- optionally commit and push changes when enabled
- optionally execute configured commands after pull and/or push
- log every important action and failure clearly
- continue running even if one repository fails
- support graceful shutdown
- be suitable for running under `systemd`, Docker, cron-supervisor patterns, or another process manager

## Non-Goals
- Do not build a full orchestration platform.
- Do not introduce a database unless there is a strong, demonstrated need.
- Do not add a web UI in the initial implementation.
- Do not support every possible Git workflow. Prefer a constrained, explicit model.
- Do not hide Git behavior behind excessive abstraction when direct subprocess calls are clearer.

## Engineering Priorities
When making tradeoffs, prefer:
1. correctness and safety
2. clear configuration and operator control
3. debuggability and logging
4. simple architecture
5. performance

## High-Level Architecture
Use a small, explicit architecture with clear boundaries:
- `config`: YAML loading and validation
- `models`: typed configuration/data models
- `scheduler`: cadence evaluation and job dispatch
- `git_ops`: pull, status, commit, push, branch checks
- `hooks`: post-pull and post-push command execution
- `service`: daemon loop, lifecycle, shutdown handling
- `logging`: structured logging setup
- `cli`: entrypoint and command-line interface

## Recommended Tech Choices
Prefer:
- Python 3.11+
- `pathlib` over raw string paths
- `subprocess.run` for Git and hook commands
- `pydantic` or dataclass-based validation for config models
- `PyYAML` or `ruamel.yaml` for YAML parsing
- standard library scheduling/time primitives unless a third-party scheduler is clearly justified
- `logging` module with structured, consistent log fields

Avoid:
- hidden global state
- implicit mutation across modules
- shell=True unless there is a compelling and documented reason
- unnecessary async code unless concurrency requirements become clear
- over-engineered plugin systems in the first version

## Python Best Practices
- Add type hints to all public functions, methods, and module-level constants where useful.
- Prefer small, single-purpose functions.
- Prefer composition over inheritance.
- Raise explicit exceptions with actionable messages.
- Catch exceptions at process boundaries, scheduler boundaries, and external-command boundaries.
- Keep side effects localized.
- Use `pathlib.Path` for filesystem work.
- Use timezone-aware timestamps where relevant.
- Keep modules focused and cohesive.
- Avoid boolean flag explosions; use named concepts or enums when behavior branches grow.

## Code Style
- Follow PEP 8.
- Format with `black`.
- Sort imports with `ruff` or `isort`.
- Lint with `ruff`.
- Type-check with `mypy` if practical.
- Use descriptive names. Favor clarity over brevity.
- Avoid comments that restate the code; add comments where behavior, intent, or safety constraints need explanation.
- Keep functions generally under ~50 lines unless there is a good reason.
- Prefer explicit return values over mutating passed-in objects.

## Repository Configuration Model
The YAML file should be the source of truth for runtime behavior.

At minimum, support per-repository fields for:
- local path
- remote name
- branch
- cadence or interval
- whether pull is enabled
- whether push is enabled
- optional commands to run after pull
- optional commands to run after push
- optional commit settings for push-enabled repos

A reasonable shape is:

```
defaults:
  interval_seconds: 300
  remote: origin
  branch: main

repositories:
  - name: dashboards
    path: /code/repo1/dashboards
    pull: true
    push: true
    interval_seconds: 300
    commit:
      enabled: true
      message: "chore: sync automated dashboard updates"
      add:
        - "."
    after_pull:
      - ["./scripts/rebuild-cache.sh"]
    after_push:
      - ["./scripts/notify.sh"]

  - name: app-config
    path: /code/repo2/app-config
    pull: true
    push: false
    interval_seconds: 900
    after_pull:
      - ["python", "scripts/refresh.py"]
```

## Configuration Rules
- Validate all YAML before starting the main service loop.
- Fail fast on invalid configuration.
- Provide clear validation errors with repository name and field path.
- Merge global defaults explicitly and predictably.
- Do not silently invent missing values when they affect safety.
- Command definitions should be structured lists of arguments unless there is a documented need for raw shell commands.
- Paths should be normalized and validated.
- Intervals must be positive and bounded to sane values.

## Git Operation Rules
- Always verify that a configured path exists and is a Git repository before attempting operations.
- Log the repository name, path, branch, and operation being performed.
- Prefer explicit Git commands over wrappers that obscure behavior.
- Check the current branch before pull/push unless detached-head support is intentionally added.
- Handle dirty working trees deliberately and predictably.
- Never auto-resolve merge conflicts.
- Never force-push unless there is an explicit, documented, opt-in setting.
- If push is enabled, define exactly when commits are created and what files are staged.
- Treat authentication and remote failures as recoverable runtime errors, not crashes of the whole service.

## Hook Command Rules
- Hooks are optional and configuration-driven.
- Hooks should run only after a successful triggering operation unless explicitly configured otherwise.
- Capture stdout, stderr, exit code, and duration for each hook.
- Log failures clearly.
- Make hook failure behavior explicit:
  - either continue and log
  - or mark the repository cycle as failed
- Do not execute hooks through a shell by default.
- Hooks should run with the repository path as working directory unless configured otherwise.

## Daemon / Service Behavior
- The service should run continuously until terminated.
- Support graceful shutdown on SIGINT and SIGTERM.
- One repository failure must not stop the whole service.
- The scheduler should track last-run and next-run times per repository.
- Use monotonic time or careful wall-clock handling to avoid drift bugs.
- Prevent overlapping runs for the same repository.
- Make concurrency a deliberate design choice. Start simple:
  - single-process
  - no overlapping per-repo jobs
  - optional threaded execution later if needed

## Observability
Log at minimum:
- service startup and shutdown
- config load success/failure
- repository cycle start and end
- pull/push attempt and result
- commit creation result
- hook execution result
- retryable failures
- skipped operations and why

Prefer structured logs or consistently formatted text logs with fields such as:
- repository
- operation
- path
- branch
- duration_ms
- result

## Error Handling
- External command failures must include command, return code, stdout, and stderr in logs where safe.
- Distinguish configuration errors, repository state errors, Git command failures, and hook failures.
- Do not swallow exceptions silently.
- Retry only where the retry behavior is clear and safe.
- Avoid infinite tight retry loops.

## Security and Safety
- Treat YAML as trusted operator input, but still validate it strictly.
- Avoid executing arbitrary shell strings when argument arrays will work.
- Do not log secrets.
- Do not assume remotes are safe or writable.
- Be careful with automated commits and pushes; make them opt-in and explicit.
- Any destructive action must require explicit configuration.

## Testing Expectations
At minimum, maintain:
- unit tests for config validation and default merging
- unit tests for scheduler cadence logic
- unit tests for Git command construction helpers
- integration-style tests against temporary local Git repositories
- tests for hook execution behavior
- tests for graceful handling of invalid repos, dirty trees, and command failures

Prefer tests that verify behavior and failure modes, not implementation details.

## CLI Expectations
Provide a small CLI with commands such as:
- `git-sentinel run --config path/to/config.yaml`
- `git-sentinel validate --config path/to/config.yaml`
- `git-sentinel once --config path/to/config.yaml [--repo NAME]`

The CLI should:
- validate config before running
- return non-zero exit codes on failure
- print actionable errors
- be friendly for systemd and container environments

## Suggested Initial Milestones
1. Config models and validation
2. Basic CLI with `validate`
3. Single repository pull loop
4. Multi-repository scheduler
5. Optional commit/push flow
6. Post-pull and post-push hooks
7. Graceful shutdown and production logging
8. Tests and packaging polish

## Definition of Done
A change is complete when:
- configuration remains explicit and validated
- code is typed and lint-clean
- tests cover both success and failure paths
- logs are sufficient to debug runtime issues
- behavior is safe for unattended execution
- documentation is updated when config or runtime behavior changes
- changes are minimal and focused; avoid unrelated refactors

## Change Guidelines for Agents
When working in this repository:
- preserve the YAML-driven architecture
- preserve unattended, daemon-like reliability as a first-class goal
- do not add complexity before it is needed
- keep Git behavior explicit and reviewable
- prefer small diffs
- update tests alongside code changes
- update documentation and example config when behavior changes

## Preferred Directory Layout
A good default layout is:

```
git-sentinel/
  AGENTS.md
  README.md
  pyproject.toml
  src/git_sentinel/
    __init__.py
    cli.py
    config.py
    models.py
    scheduler.py
    service.py
    git_ops.py
    hooks.py
    logging_config.py
  tests/
    test_config.py
    test_scheduler.py
    test_git_ops.py
    test_hooks.py
    test_service.py
  examples/
    config.example.yaml
```

## Commands
Prefer these development commands if the repo is set up for them:
- format: `black .`
- lint: `ruff check .`
- fix lint issues: `ruff check . --fix`
- type check: `mypy src`
- test: `pytest`
- test with coverage: `pytest --cov=git_sentinel --cov-report=term-missing`

## Notes for Future Contributors
- Keep the operator experience boring and dependable.
- Every automation feature should be auditable through config and logs.
- Favor explicit scheduling and explicit Git behavior over magic.
- This project should feel safe to leave running for months.