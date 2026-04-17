"""Canonical Python fixture for dry-run sandbox.

Hooks invoked via dry_run.run_for receive a temp copy of this file in a
freshly-created tempdir. Real hook commands (ruff, mypy, etc.) should not
mutate the repo source.
"""


def hello() -> str:
    return "world"
