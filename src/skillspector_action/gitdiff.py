from __future__ import annotations

import subprocess
from pathlib import Path


def changed_files_from_git(repo: Path | str, base_ref: str, head_ref: str = "HEAD") -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{base_ref}...{head_ref}"],
        cwd=Path(repo),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def fetch_ref(repo: Path | str, remote: str, ref: str) -> bool:
    result = subprocess.run(
        ["git", "fetch", "--no-tags", "--depth=1", remote, ref],
        cwd=Path(repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.returncode == 0
