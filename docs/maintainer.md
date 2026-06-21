# Maintainer Guide

This document is for maintainers of `NPJigaK/skillspector-action`.

## Runtime image

The action is a composite action that runs a containerized scanner wrapper. The default runtime image is published to GHCR:

```text
ghcr.io/npjigak/skillspector-action
```

Normal users do not need to know or configure this image. The `image` input exists for development and debugging only.

## Release process

1. Make sure `main` is green.
2. Create and push a semantic version tag, for example:

```bash
git tag v1.0.0
git push origin v1.0.0
```

3. Move or create the matching major action tag:

```bash
git tag -f v1 v1.0.0
git push -f origin v1
```

4. Confirm `.github/workflows/publish-image.yml` succeeds.

## Published image tags

The publish workflow emits:

- branch tags such as `main`;
- semantic version tags such as `1.0.0` and `v1.0.0`;
- major tags such as `1` and `v1`;
- commit tags such as `sha-<commit>`.

The `v*` image tags matter because users normally call the action as:

```yaml
uses: NPJigaK/skillspector-action@v1
```

That action ref resolves to the matching `v1` runtime image tag.

## SkillSpector pin

The Dockerfile pins upstream SkillSpector with `SKILLSPECTOR_REF`.

When updating the pin:

1. Update `Dockerfile`.
2. Update `tests/test_workflows.py`.
3. Run `python -m pytest -q`.
4. Confirm the PR CI builds the Docker image.

## Development image override

The hidden `image` input can be used to test an unpublished runtime image:

```yaml
- uses: NPJigaK/skillspector-action@v1
  with:
    image: ghcr.io/npjigak/skillspector-action:main
```

Do not recommend this input in user-facing setup docs.
