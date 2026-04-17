"""Git-compatible blob SHA-1 hashing.

Implements the `blob {len}\\0{content}` framing used by
`git hash-object`, so our SHAs match what git would compute.
Falls back to in-process implementation if git is unavailable.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


def git_blob_sha_bytes(content: bytes) -> str:
    """Compute git blob SHA-1 over raw bytes.

    Format: ``sha1(b"blob " + str(len(content)).encode() + b"\\x00" + content)``
    """
    header = f"blob {len(content)}\x00".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def git_blob_sha(path: Path) -> str:
    """Compute git blob SHA-1 for the file at ``path``.

    Reads bytes verbatim — no newline normalisation, no encoding
    conversion. Matches `git hash-object` output for any committed
    file with default git config.
    """
    return git_blob_sha_bytes(path.read_bytes())
