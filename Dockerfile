FROM python:3.12-slim-bookworm

ARG SKILLSPECTOR_REF=a5092dd9b9521ff57a9b53612bb129ce78019002

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /opt/skillspector-action

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential git \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip \
    && python -m pip install "git+https://github.com/NVIDIA/SkillSpector.git@${SKILLSPECTOR_REF}"

COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install .

COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
