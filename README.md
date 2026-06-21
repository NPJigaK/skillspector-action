# skillspector-action

Scan AI agent skills with [NVIDIA SkillSpector](https://github.com/NVIDIA/SkillSpector) from GitHub Actions.

This action is for skill authors and skill registry maintainers who want a simple CI check for `SKILL.md` repositories. It runs static analysis by default, uploads reports, and only fails CI when you ask it to.

## Quick start

```yaml
name: SkillSpector

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read
  security-events: write # only needed when upload-sarif is true

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

By default the action reports findings without failing CI:

```yaml
fail-on: none
```

Fail CI only for the severities you care about:

```yaml
- uses: NPJigaK/skillspector-action@v1
  with:
    path: .
    changed-only: true
    fail-on: critical
    upload-sarif: true
```

## What you get

- Automatic `SKILL.md` discovery under `path`.
- Static SkillSpector scanning by default, without LLM API keys.
- Pull request mode with `changed-only: true`.
- JSON, SARIF, Markdown summary, and artifact reports.
- Optional GitHub Code Scanning upload.
- Opt-in CI failure with `fail-on` or `min-score`.

## Examples

These pull requests show the released `@v1` action wired into real skill repositories:

- [jq-cli-skill #7](https://github.com/NPJigaK/jq-cli-skill/pull/7)
- [unified-adversarial-review-skill #10](https://github.com/NPJigaK/unified-adversarial-review-skill/pull/10)

Use the Quick start workflow above for your own repository.

## Inputs

| Input | Default | Description |
| --- | --- | --- |
| `path` | `.` | Repository path or `SKILL.md` file to scan. |
| `changed-only` | `false` | On pull requests, scan only changed skill directories. |
| `fail-on` | `none` | One of `none`, `high`, or `critical`. |
| `min-score` | empty | Optional numeric risk score threshold that fails the action. |
| `upload-sarif` | `false` | Upload the SARIF report to GitHub Code Scanning. |
| `exclude` | empty | Newline or comma separated glob patterns to exclude. |
| `baseline` | empty | Optional baseline file for suppressing accepted findings. |
| `llm` | `false` | Enable SkillSpector LLM analysis. Static mode is used by default. |
| `artifact-name` | `skillspector-results` | Artifact name for generated reports. |

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

For artifact and summary reports only:

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

## Security notes

Use `pull_request`, not `pull_request_target`, when scanning untrusted pull request code.

`llm` defaults to `false`. Do not pass LLM API keys to workflows that run on untrusted fork pull requests.

For high-security environments, pin third-party actions to full commit SHAs.

## More documentation

- [Advanced usage](docs/advanced-usage.md): baseline, exclude patterns, LLM scans, and pinning.
- [Maintainer guide](docs/maintainer.md): releases, runtime image publishing, and implementation notes.
