# skillspector-action

GitHub Action for scanning AI agent skills with [NVIDIA SkillSpector](https://github.com/NVIDIA/SkillSpector).

This action is unofficial and experimental. It is designed for skill authors, skill registries, and internal AI agent platform teams that want a normal GitHub Actions experience without installing SkillSpector in every workflow.

## Quick start

```yaml
name: SkillSpector

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read
  security-events: write # required only when upload-sarif is true

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: NPJigaK/skillspector-action@v1
        with:
          path: .
          changed-only: true
          upload-sarif: true
```

Default behavior is report-only:

```yaml
fail-on: none
```

Use `fail-on` or `min-score` when you want CI to fail:

```yaml
- uses: NPJigaK/skillspector-action@v1
  with:
    path: .
    changed-only: true
    fail-on: critical
    min-score: "90"
    upload-sarif: true
```

## What it does

- Finds `SKILL.md` files under `path`.
- Runs SkillSpector static analysis by default with `--no-llm`.
- On pull requests, `changed-only: true` scans only changed skill directories.
- Writes JSON, SARIF, and Markdown reports to `skillspector-results`.
- Uploads reports as a workflow artifact.
- Optionally uploads SARIF to GitHub Code Scanning.
- Fails only when `fail-on` or `min-score` says to fail.

## Inputs

| Input | Default | Description |
| --- | --- | --- |
| `path` | `.` | Repository path or `SKILL.md` file to scan. |
| `changed-only` | `false` | On pull requests, scan only changed skill directories. If the PR diff cannot be resolved, the action falls back to full discovery. |
| `fail-on` | `none` | One of `none`, `high`, or `critical`. |
| `min-score` | empty | Optional numeric risk score threshold that fails the action. |
| `upload-sarif` | `false` | Upload `results.sarif` with `github/codeql-action/upload-sarif@v4`. |
| `exclude` | empty | Newline or comma separated glob patterns to exclude. |
| `baseline` | empty | Optional baseline JSON path for suppressing accepted findings. |
| `llm` | `false` | Enable SkillSpector LLM analysis. Static mode is used by default. |
| `artifact-name` | `skillspector-results` | Artifact name for generated reports. |
| `image` | empty | Override the scanner image for development. Normal users should not set this. |

## Outputs

| Output | Description |
| --- | --- |
| `sarif` | Path to the generated SARIF report. |
| `json` | Path to the generated JSON report. |
| `markdown` | Path to the Markdown summary. |
| `risk-score` | Highest risk score across scanned skills. |
| `risk-severity` | Highest risk severity across scanned skills. |
| `findings-count` | Finding count after suppressions. |
| `scanned-count` | Number of skill targets scanned. |

## Permissions

For local reports only:

```yaml
permissions:
  contents: read
```

For Code Scanning upload:

```yaml
permissions:
  contents: read
  security-events: write
```

Code Scanning is available for public repositories on GitHub.com and for organization-owned repositories with GitHub Code Security enabled.

## Security notes

Use `pull_request`, not `pull_request_target`, when scanning untrusted pull request code. A privileged `pull_request_target` workflow that checks out fork code can expose write tokens and secrets to attacker-controlled content.

`llm` defaults to `false`. Do not pass LLM API keys to workflows that run on untrusted fork pull requests. When `llm: false`, this action does not pass common LLM provider environment variables into the scanner container.

For high-security environments, pin third-party actions to full commit SHAs. When this action is called by a full commit SHA, it resolves the default runtime image to `ghcr.io/npjigak/skillspector-action:sha-<commit>`. Tag users such as `@v1` receive the matching `v1` image tag.

## GHCR and cost

The scanner runtime is published as a public GHCR image. Users do not need to pull it manually or authenticate to GHCR. GitHub public packages are free to use, and public container images can be pulled anonymously.

The workflow still consumes the caller repository's normal GitHub Actions usage. Public repositories using standard GitHub-hosted runners are free; private repositories use the account or organization Actions allowance and billing settings.

## Baseline

Use `baseline` to suppress findings that were already reviewed and accepted.

```json
{
  "version": 1,
  "findings": [
    {
      "rule_id": "SS001",
      "path": "skills/example/SKILL.md",
      "message_hash": "0123456789abcdef"
    }
  ]
}
```

`message_hash` is a SHA-256 prefix of the normalized finding message. Suppressed findings are excluded from failure decisions and counted separately in `results.json` and the job summary.

## Release process

This repository publishes `ghcr.io/npjigak/skillspector-action` from `.github/workflows/publish-image.yml`.

Published tags include:

- branch tags such as `main`;
- semantic versions such as `1.0.0`;
- major versions such as `1`;
- commit tags such as `sha-<commit>`.

Create a `v1.0.0` Git tag and move the `v1` action tag when publishing a compatible release.
