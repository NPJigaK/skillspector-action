# SkillSpector Action Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a distributable GitHub Action that runs SkillSpector from a public GHCR image, discovers skill targets, produces JSON/SARIF/Markdown reports, optionally uploads SARIF, and fails only when configured.

**Architecture:** A composite `action.yml` invokes a runner-side shell script that computes the scanner image and runs it with `docker run`. The image contains a Python wrapper package that performs discovery, changed-only diffing, SkillSpector invocation, suppression, report merging, summary generation, and failure policy. The wrapper normalizes SARIF into a single run and the publish workflow publishes branch, semver, major, and `sha-<commit>` image tags.

**Tech Stack:** GitHub composite actions, Docker/GHCR, Python 3.12, pytest, shell scripts, GitHub CodeQL `upload-sarif@v4`, `actions/upload-artifact@v4`, Docker Buildx.

---

## Review Constraints

The implementation must address the adversarial review findings before it can be considered complete:

- Avoid a hardcoded mutable runtime image in `action.yml`. Use `docker run` from a shell script so the default image can be derived from `github.action_ref`.
- Publish and consume `sha-<commit>` image tags when the action is pinned by full commit SHA.
- Merge per-target SARIF output into one SARIF run to avoid GitHub Code Scanning multi-run/category upload failures.
- For `changed-only`, fetch the PR base SHA when needed and fall back to full discovery rather than skipping scans when the diff cannot be resolved.
- Do not pass LLM-related environment variables into the container unless `llm` is explicitly true.

## File Structure

- Create `action.yml`: public action inputs/outputs and composite steps for running the container, uploading artifacts, and uploading SARIF.
- Create `scripts/run-action.sh`: runner-side image resolution, docker invocation, and output forwarding.
- Create `scripts/entrypoint.sh`: container entrypoint that invokes the Python wrapper.
- Create `Dockerfile`: Python 3.12 runtime with SkillSpector installed from pinned commit `a5092dd9b9521ff57a9b53612bb129ce78019002`.
- Create `pyproject.toml`: local package and pytest config for the wrapper.
- Create `src/skillspector_action/__init__.py`: package marker and version.
- Create `src/skillspector_action/__main__.py`: CLI entrypoint.
- Create `src/skillspector_action/config.py`: typed config parsing.
- Create `src/skillspector_action/discovery.py`: skill target discovery and changed-file mapping.
- Create `src/skillspector_action/baseline.py`: baseline loading and finding suppression keys.
- Create `src/skillspector_action/reports.py`: JSON/SARIF normalization and Markdown summary generation.
- Create `src/skillspector_action/runner.py`: SkillSpector subprocess orchestration and failure decision.
- Create tests under `tests/` for discovery, baseline, reports, policy, and CLI smoke behavior.
- Create `.github/workflows/ci.yml`: run unit tests and action smoke checks.
- Create `.github/workflows/publish-image.yml`: publish the GHCR image on pushes and tags.
- Replace `README.md`: user-facing examples, inputs, outputs, security notes, billing/availability notes, and release process.

### Task 1: Project Skeleton and Discovery

**Files:**
- Create: `pyproject.toml`
- Create: `src/skillspector_action/__init__.py`
- Create: `src/skillspector_action/discovery.py`
- Test: `tests/test_discovery.py`

- [ ] **Step 1: Write failing discovery tests**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_discovery.py -q`

Expected: import failure for `skillspector_action.discovery`.

- [ ] **Step 3: Implement minimal discovery**

Create `pyproject.toml` with pytest path setup, package metadata, and Python 3.12 target. Implement `discover_skill_targets(root, excludes=())` and `targets_for_changed_files(root, changed_files, excludes=())` using `Path.rglob("SKILL.md")`, stable sorting, and parent walking to find the nearest owning `SKILL.md`.

- [ ] **Step 4: Run discovery tests**

Run: `python -m pytest tests/test_discovery.py -q`

Expected: 3 passed.

### Task 2: Excludes and Changed-Only Diff

**Files:**
- Modify: `src/skillspector_action/discovery.py`
- Create: `src/skillspector_action/gitdiff.py`
- Test: `tests/test_discovery.py`
- Test: `tests/test_gitdiff.py`

- [ ] **Step 1: Write failing exclude and diff tests**

Add tests proving comma/newline exclude patterns skip matching targets and that `changed_files_from_git()` returns changed paths from a temporary git repo.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_discovery.py tests/test_gitdiff.py -q`

Expected: missing `gitdiff` module or exclude behavior failure.

- [ ] **Step 3: Implement excludes and git diff helper**

Use `fnmatch.fnmatch` against both POSIX relative target paths and file paths. Implement `changed_files_from_git(repo, base_ref, head_ref="HEAD")` with `git diff --name-only --diff-filter=ACMR`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_discovery.py tests/test_gitdiff.py -q`

Expected: all tests pass.

### Task 3: Baseline Suppression

**Files:**
- Create: `src/skillspector_action/baseline.py`
- Test: `tests/test_baseline.py`

- [ ] **Step 1: Write failing baseline tests**

Test that a baseline entry matching `rule_id`, normalized path, and message fingerprint suppresses a finding, and non-matching findings remain active.

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_baseline.py -q`

Expected: import failure for `skillspector_action.baseline`.

- [ ] **Step 3: Implement baseline matching**

Implement baseline JSON shape:

```json
{
  "version": 1,
  "findings": [
    {
      "rule_id": "SS001",
      "path": "skills/alpha/SKILL.md",
      "message_hash": "sha256-prefix"
    }
  ]
}
```

Normalize paths to POSIX relative paths and hash normalized messages with SHA-256.

- [ ] **Step 4: Run baseline tests**

Run: `python -m pytest tests/test_baseline.py -q`

Expected: all tests pass.

### Task 4: Report Merging and Summary

**Files:**
- Create: `src/skillspector_action/reports.py`
- Test: `tests/test_reports.py`

- [ ] **Step 1: Write failing report tests**

Test that multiple SkillSpector-like JSON reports are combined, highest severity and score are computed, and multiple SARIF inputs become one SARIF `run` with deduplicated rules and merged results.

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_reports.py -q`

Expected: import failure for `skillspector_action.reports`.

- [ ] **Step 3: Implement report utilities**

Implement:

- `merge_json_reports(reports, suppressed_findings)`
- `merge_sarif_reports(reports)`
- `write_markdown_summary(summary)`
- severity ordering `none < low < medium < high < critical`

The SARIF merger must emit SARIF version `2.1.0`, one run, one `tool.driver`, deduplicated `rules`, and all results.

- [ ] **Step 4: Run report tests**

Run: `python -m pytest tests/test_reports.py -q`

Expected: all tests pass.

### Task 5: Failure Policy and Wrapper CLI

**Files:**
- Create: `src/skillspector_action/config.py`
- Create: `src/skillspector_action/runner.py`
- Create: `src/skillspector_action/__main__.py`
- Test: `tests/test_policy.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing policy and CLI tests**

Test `fail-on: none`, `high`, `critical`, `min-score`, empty target success, and CLI output files using a fake scanner callable.

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_policy.py tests/test_cli.py -q`

Expected: missing modules or missing CLI behavior.

- [ ] **Step 3: Implement config, policy, and CLI orchestration**

Parse environment variables from the action:

- `INPUT_PATH`
- `INPUT_CHANGED_ONLY`
- `INPUT_FAIL_ON`
- `INPUT_MIN_SCORE`
- `INPUT_EXCLUDE`
- `INPUT_BASELINE`
- `INPUT_LLM`
- `INPUT_OUTPUT_DIR`

Run SkillSpector through `subprocess.run`, write per-target JSON/SARIF under a temporary directory, apply suppressions, merge final reports, write `$GITHUB_OUTPUT` values when present, append Markdown to `$GITHUB_STEP_SUMMARY` when present, and exit non-zero only for configured policy failures or scanner execution errors.

- [ ] **Step 4: Run policy and CLI tests**

Run: `python -m pytest tests/test_policy.py tests/test_cli.py -q`

Expected: all tests pass.

### Task 6: Action Metadata and Shell Entrypoints

**Files:**
- Create: `action.yml`
- Create: `scripts/run-action.sh`
- Create: `scripts/entrypoint.sh`
- Test: `tests/test_action_metadata.py`

- [ ] **Step 1: Write failing metadata tests**

Test that `action.yml` declares the planned inputs/outputs, uses composite, includes artifact upload, includes SARIF upload with `github/codeql-action/upload-sarif@v4`, and does not hardcode `docker://ghcr.io/npjigak/skillspector-action:v1`.

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_action_metadata.py -q`

Expected: `action.yml` missing.

- [ ] **Step 3: Implement action and scripts**

`scripts/run-action.sh` computes the default image:

- if `INPUT_IMAGE` is set, use it;
- else if `ACTION_REF` is a 40-character hex SHA, use `ghcr.io/npjigak/skillspector-action:sha-${ACTION_REF}`;
- else use `ghcr.io/npjigak/skillspector-action:${ACTION_REF:-v1}`.

It runs Docker with the workspace mounted read-write only for report output, passes action inputs, and passes LLM provider environment variables only when `INPUT_LLM=true`.

`action.yml` uses a composite `run` step for the shell script, `actions/upload-artifact@v4`, and conditional `github/codeql-action/upload-sarif@v4`.

- [ ] **Step 4: Run metadata tests**

Run: `python -m pytest tests/test_action_metadata.py -q`

Expected: tests pass.

### Task 7: Dockerfile and CI

**Files:**
- Create: `Dockerfile`
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/publish-image.yml`
- Test: `tests/test_workflows.py`

- [ ] **Step 1: Write failing workflow tests**

Test that Dockerfile pins `SKILLSPECTOR_REF` to `a5092dd9b9521ff57a9b53612bb129ce78019002`, CI runs pytest, and publish workflow includes `packages: write`, GHCR login, build-push-action, semver tags, major tags, and `sha-{{sha}}` tags.

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_workflows.py -q`

Expected: files missing.

- [ ] **Step 3: Implement Dockerfile and workflows**

Use `python:3.12-slim-bookworm`, install git, install this package, install SkillSpector from pinned Git commit, and set `/entrypoint.sh`. Configure CI for Python tests and a container build smoke test. Configure publish image on branch and tag pushes.

- [ ] **Step 4: Run workflow tests**

Run: `python -m pytest tests/test_workflows.py -q`

Expected: tests pass.

### Task 8: README and Smoke Verification

**Files:**
- Modify: `README.md`
- Test: all tests

- [ ] **Step 1: Write failing README tests**

Add test assertions that README documents basic usage, permissions, inputs, outputs, `pull_request` guidance, `pull_request_target` warning, GHCR public/free note, and LLM opt-in warning.

- [ ] **Step 2: Run README test to verify failure**

Run: `python -m pytest tests/test_readme.py -q`

Expected: README content missing.

- [ ] **Step 3: Replace README**

Write a complete README with:

- copy-paste workflow;
- report-only default;
- CI failure examples;
- changed-only behavior;
- SARIF upload permissions;
- LLM opt-in and fork PR warnings;
- billing and GHCR notes;
- release and image publishing notes;
- baseline format.

- [ ] **Step 4: Run full verification**

Run:

```bash
python -m pytest -q
docker build -t skillspector-action:test .
```

Expected: pytest passes and Docker image builds successfully.

### Task 9: Final Self-Review and Completion Check

**Files:**
- Review all modified files.

- [ ] **Step 1: Run unified adversarial review**

Review the final diff read-only for ship-blocking risks, focusing on GitHub Actions security, SARIF upload reliability, Docker runtime behavior, and changed-only correctness.

- [ ] **Step 2: Digest findings**

Accept only grounded material findings and fix them with TDD when they touch code.

- [ ] **Step 3: Run final verification**

Run:

```bash
python -m pytest -q
docker build -t skillspector-action:test .
git diff --check
```

Expected: all commands succeed.

- [ ] **Step 4: Report completion**

Summarize changed files, verification evidence, and any remaining release steps such as tagging and pushing the GHCR image.
