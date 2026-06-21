from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable


def discover_skill_targets(root: Path | str, excludes: Iterable[str] = ()) -> list[Path]:
    scan_root = Path(root)
    patterns = tuple(pattern for pattern in excludes if pattern)

    if scan_root.is_file():
        return [] if _is_excluded(scan_root, scan_root.parent, patterns) else [scan_root]

    targets = []
    for skill_file in scan_root.rglob("SKILL.md"):
        target = skill_file.parent
        if not _is_excluded(target, scan_root, patterns) and not _is_excluded(skill_file, scan_root, patterns):
            targets.append(target)

    return sorted(set(targets), key=lambda path: path.as_posix())


def targets_for_changed_files(
    root: Path | str,
    changed_files: Iterable[str],
    excludes: Iterable[str] = (),
) -> list[Path]:
    scan_root = Path(root)
    patterns = tuple(pattern for pattern in excludes if pattern)
    targets: set[Path] = set()

    for changed_file in changed_files:
        candidate = (scan_root / changed_file).resolve()
        target = _owning_skill_target(scan_root.resolve(), candidate)
        if target is None:
            continue
        if _is_excluded(target, scan_root, patterns) or _is_excluded(candidate, scan_root, patterns):
            continue
        targets.add(target)

    return sorted(targets, key=lambda path: path.as_posix())


def _owning_skill_target(root: Path, path: Path) -> Path | None:
    current = path if path.is_dir() else path.parent
    while True:
        if (current / "SKILL.md").exists():
            return current
        if current == root or current.parent == current:
            return None
        current = current.parent


def _is_excluded(path: Path, root: Path, patterns: tuple[str, ...]) -> bool:
    if not patterns:
        return False
    rel_path = _relative_posix(path, root)
    return any(fnmatch(rel_path, pattern) or fnmatch(path.name, pattern) for pattern in patterns)


def _relative_posix(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
