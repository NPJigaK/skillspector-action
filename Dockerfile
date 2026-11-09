FROM python:3.12-slim-bookworm

ARG SKILLSPECTOR_VERSION=2.13.4
ARG SKILLSPECTOR_REF=54824463814a0be01360792523ec7245a69190fc

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /opt/skillspector-action

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential git \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip \
    && python -m pip install "git+https://github.com/NVIDIA/SkillSpector.git@${SKILLSPECTOR_REF}" \
    && python -c "from importlib.metadata import version; assert version('skillspector') == '${SKILLSPECTOR_VERSION}'"

COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install .

COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
