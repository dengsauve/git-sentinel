# git-sentinel

`git-sentinel` is a daemon-like Python service that manages one or more Git
repositories from a YAML configuration file. It is designed for unattended,
boring automation: pull on a cadence, optionally create commits and push, and
optionally run hooks after successful operations.

## Features

- strict YAML configuration validation before work starts
- explicit pull, status, commit, and push operations via `git`
- optional post-pull and post-push hooks
- single-process scheduler with no overlapping runs per repository
- graceful shutdown on `SIGINT` and `SIGTERM`
- CLI commands for validation, one-shot execution, and continuous service mode

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

## Usage

Start by copying and editing the example configuration:

```bash
cp examples/config.example.yaml /path/to/config.yaml
```

Update each repository entry so `path`, `branch`, cadence, and optional
commit/hook settings match the repositories you want to manage.

Validate the configuration before running the service:

```bash
.venv/bin/git-sentinel validate --config /path/to/config.yaml
```

Run one repository cycle for every configured repository:

```bash
.venv/bin/git-sentinel once --config /path/to/config.yaml
```

Run one repository cycle for a single repository by name:

```bash
.venv/bin/git-sentinel once --config /path/to/config.yaml --repo dashboards
```

Run the long-lived service:

```bash
.venv/bin/git-sentinel run --config /path/to/config.yaml
```

Enable verbose logging while validating or running:

```bash
.venv/bin/git-sentinel --verbose validate --config /path/to/config.yaml
.venv/bin/git-sentinel --verbose run --config /path/to/config.yaml
```

## Configuration

See [`examples/config.example.yaml`](examples/config.example.yaml).

Configuration is merged from `defaults` into each repository definition. The
service validates:

- required repository fields such as `name` and `path`
- positive, bounded intervals
- command arguments as structured string arrays
- explicit commit configuration for push-enabled repositories

## Running Tests

Run the full test suite:

```bash
.venv/bin/python -m pytest
```

Run tests with coverage:

```bash
.venv/bin/python -m pytest --cov=git_sentinel --cov-report=term-missing
```

## Development

```bash
.venv/bin/python -m black .
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy src
.venv/bin/python -m pytest
```
