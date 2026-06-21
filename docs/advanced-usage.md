# Advanced Usage

This page covers options most users do not need on their first setup.

## Changed-only scanning

Use `changed-only: true` on pull requests to scan only skill directories touched by the PR.

```yaml
- uses: NPJigaK/skillspector-action@v1
  with:
    path: .
    changed-only: true
```

If the pull request diff cannot be resolved, the action falls back to full skill discovery instead of skipping scans.

## Exclude patterns

Use `exclude` to skip generated or vendored skill directories.

```yaml
- uses: NPJigaK/skillspector-action@v1
  with:
    exclude: |
      vendor/**
      archived/**
```

Patterns are matched against repository-relative paths using shell-style globs.

## Baseline

Use `baseline` when a finding has already been reviewed and accepted.

```yaml
- uses: NPJigaK/skillspector-action@v1
  with:
    baseline: .skillspector-baseline.json
```

Baseline file format:

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

`message_hash` is a SHA-256 prefix of the normalized finding message. Suppressed findings are removed from JSON/SARIF failure decisions and counted separately in the summary.

## LLM scans

Static mode is the default. Enable LLM analysis only when the workflow can safely access the required provider credentials.

```yaml
- uses: NPJigaK/skillspector-action@v1
  with:
    llm: true
```

Do not enable LLM scans for untrusted fork pull requests if the job has access to API keys.

## Pinning

For high-security workflows, pin actions to full commit SHAs:

```yaml
- uses: NPJigaK/skillspector-action@<full-commit-sha>
```

When called by a full commit SHA, the action resolves the matching runtime image tag for that commit.
