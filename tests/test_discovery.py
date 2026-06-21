from pathlib import Path

from skillspector_action.discovery import discover_skill_targets, targets_for_changed_files


def test_discovers_skill_directories(tmp_path: Path) -> None:
    (tmp_path / "skills" / "alpha").mkdir(parents=True)
    (tmp_path / "skills" / "alpha" / "SKILL.md").write_text("# Alpha\n", encoding="utf-8")
    (tmp_path / "skills" / "beta").mkdir(parents=True)
    (tmp_path / "skills" / "beta" / "SKILL.md").write_text("# Beta\n", encoding="utf-8")

    assert discover_skill_targets(tmp_path) == [
        tmp_path / "skills" / "alpha",
        tmp_path / "skills" / "beta",
    ]


def test_single_skill_file_is_a_target(tmp_path: Path) -> None:
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("# Root\n", encoding="utf-8")

    assert discover_skill_targets(skill_file) == [skill_file]


def test_changed_files_map_to_owning_skill_directory(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "alpha"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Alpha\n", encoding="utf-8")
    (skill_dir / "notes.md").write_text("notes\n", encoding="utf-8")

    assert targets_for_changed_files(tmp_path, ["skills/alpha/notes.md"]) == [skill_dir]


def test_excludes_remove_discovered_and_changed_targets(tmp_path: Path) -> None:
    alpha = tmp_path / "skills" / "alpha"
    beta = tmp_path / "skills" / "beta"
    alpha.mkdir(parents=True)
    beta.mkdir(parents=True)
    (alpha / "SKILL.md").write_text("# Alpha\n", encoding="utf-8")
    (beta / "SKILL.md").write_text("# Beta\n", encoding="utf-8")

    assert discover_skill_targets(tmp_path, excludes=["skills/beta/**", "skills/beta"]) == [alpha]
    assert targets_for_changed_files(
        tmp_path,
        ["skills/alpha/SKILL.md", "skills/beta/SKILL.md"],
        excludes=["skills/beta/**", "skills/beta"],
    ) == [alpha]
