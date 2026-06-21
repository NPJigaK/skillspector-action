# SkillSpector Action Design

## Goal

Build a distributable GitHub Action for running NVIDIA SkillSpector in skill distribution repositories and CI pipelines with a normal `uses:` experience:

```yaml
- uses: NPJigaK/skillspector-action@v1
  with:
    path: .
    changed-only: true
    fail-on: critical
    upload-sarif: true
```

The action should feel like a standard GitHub Action. Users should not need to understand GHCR, Docker image publishing, or SkillSpector installation details.

## Positioning

This is an unofficial, experimental integration around SkillSpector. The value is not only wrapping the CLI, but giving skill authors and registry maintainers a PR security-check workflow with safe defaults:

- API-key-free scanning by default with SkillSpector `--no-llm`.
- Report-only default so CI does not fail unless explicitly configured.
- SARIF support for GitHub Code Scanning.
- Changed-skill scanning for pull requests.
- JSON, SARIF, Markdown summary, and artifacts for triage.
- Suppression hooks through excludes and baselines to reduce false positives.

## Architecture

Use a Composite Action backed by a published GHCR image.

The repository will publish a public container image at:

```text
ghcr.io/npjigak/skillspector-action:<version>
```

The composite action hides that image from users. It prepares inputs, runs the containerized scanner, optionally uploads SARIF through `github/codeql-action/upload-sarif`, and exposes outputs. The GHCR image contains the pinned SkillSpector runtime and this action's scanner wrapper.

This gives users a one-step `uses:` interface while keeping runtime dependencies controlled by this repository.

## User Experience

The minimal user workflow is:

```yaml
name: SkillSpector

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read
  security-events: write

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: NPJigaK/skillspector-action@v1
        with:
          path: .
          changed-only: true
          upload-sarif: true
```

Users only configure action inputs. They do not pull the GHCR image directly.

## Inputs

The MVP action supports:

- `path`: scan root, default `.`.
- `changed-only`: when true on pull requests, scan only changed skill directories, default `false`.
- `fail-on`: one of `none`, `high`, `critical`, default `none`.
- `min-score`: optional numeric risk score threshold for failure, default unset.
- `upload-sarif`: whether to upload SARIF to GitHub Code Scanning, default `false`.
- `exclude`: newline or comma separated glob patterns to skip, default empty.
- `baseline`: optional path to a baseline JSON file for suppressing already accepted findings, default empty.
- `llm`: enable SkillSpector LLM analysis, default `false`.
- `artifact-name`: artifact name for generated reports, default `skillspector-results`.
- `image`: override scanner image for development, default to this repository's public GHCR image.

## Outputs

The action exposes:

- `sarif`: path to the generated SARIF report.
- `json`: path to the generated JSON report.
- `markdown`: path to the Markdown summary.
- `risk-score`: highest risk score found across scanned skills.
- `risk-severity`: highest severity found across scanned skills.
- `findings-count`: total finding count after suppressions.
- `scanned-count`: number of skill targets scanned.

## Scan Target Discovery

The scanner wrapper discovers skill targets by finding `SKILL.md` files under `path`.

When `changed-only` is false, it scans each discovered skill directory. If `path` itself is a single `SKILL.md`, it scans that file.

When `changed-only` is true on a pull request, it compares the PR diff against the base ref and scans only skill directories whose files changed. If changed-only discovery finds no changed skill targets, the action exits successfully with an empty report and a clear summary.

For non-PR events with `changed-only: true`, the action falls back to full discovery unless a base commit is available.

## Report Generation

For each target, the wrapper runs SkillSpector in static mode by default:

```bash
skillspector scan <target> --no-llm --format json --output <target-report.json>
skillspector scan <target> --no-llm --format sarif --output <target-report.sarif>
```

If `llm: true`, it omits `--no-llm` and relies on caller-provided environment variables or secrets. The README must warn users not to pass LLM credentials to untrusted fork PRs.

The wrapper merges per-target outputs into:

- `skillspector-results/results.json`
- `skillspector-results/results.sarif`
- `skillspector-results/summary.md`

The job summary displays the Markdown summary.

## Failure Policy

Default behavior is report-only:

```yaml
fail-on: none
```

Failure is opt-in:

- `fail-on: high` fails when any finding severity is `high` or `critical`.
- `fail-on: critical` fails when any finding severity is `critical`.
- `min-score` fails when the highest risk score is greater than or equal to the configured threshold.

If both `fail-on` and `min-score` are configured, either condition can fail the action.

## Suppression Policy

The MVP supports two suppression mechanisms:

- `exclude` prevents target discovery and report inclusion for matching paths.
- `baseline` suppresses findings matching a stable key built from rule id, normalized file path, and message fingerprint.

Suppressed findings are omitted from failure decisions but counted separately in JSON and summary output. The baseline format is owned by this action so it can remain stable even if SkillSpector report details change.

## Security Defaults

The action follows conservative CI defaults:

- `llm` defaults to `false`.
- `fail-on` defaults to `none`.
- Recommended workflow permissions are `contents: read`; `security-events: write` is only required when SARIF upload is enabled.
- Documentation must recommend `pull_request`, not privileged `pull_request_target`, for scanning untrusted PR code.
- Documentation must recommend pinning third-party actions to a full commit SHA in high-security environments.
- The publish workflow should pin the upstream SkillSpector source by commit SHA or a controlled build argument.
- The published image should be public so users do not need registry credentials.

## Repository Files

Expected implementation files:

- `action.yml`: composite action metadata and public inputs/outputs.
- `Dockerfile`: scanner runtime image with SkillSpector installed.
- `scripts/entrypoint.sh`: container entrypoint that invokes the scanner wrapper.
- `src/skillspector_action/`: Python scanner wrapper package.
- `tests/`: unit tests for discovery, suppression, SARIF/JSON merging, and failure policy.
- `.github/workflows/ci.yml`: test workflow for this action repo.
- `.github/workflows/publish-image.yml`: GHCR publish workflow for tags/releases.
- `README.md`: usage, inputs, outputs, security notes, and examples.

## Publishing

This repository publishes the runtime image to GHCR using GitHub Actions. Tags should include:

- commit SHA for immutable development builds.
- semantic version tags such as `v1.0.0`.
- major version tag such as `v1`.

The action should default to the major version image for normal users, while advanced users can override `image` for testing.

## Testing Strategy

Use test-driven implementation for wrapper behavior:

- Discovery finds skill directories from `SKILL.md`.
- Changed-only scanning maps changed files to owning skill directories.
- Exclude patterns remove targets.
- Baseline suppresses matching findings.
- Failure policy handles `none`, `high`, `critical`, and score threshold.
- Report merger produces valid JSON and SARIF structures.

Use CI to run unit tests and a smoke test against a tiny fixture skill. Image publishing should run only after tests pass.

## Non-Goals for MVP

- Marketplace publication polish beyond usable metadata.
- Advanced PR annotations outside SARIF.
- Auto-generating baseline files.
- Full LLM provider setup.
- Non-GitHub CI support.
- Reimplementing SkillSpector detection logic.

## References

- SkillSpector supports directory, file, URL, zip, JSON, Markdown, SARIF, and `--no-llm` scanning.
- GitHub public packages are free to use, and public container images can be pulled anonymously.
- GitHub Actions usage remains the caller repository's normal Actions usage.
- SARIF upload uses `github/codeql-action/upload-sarif` with `security-events: write`.
