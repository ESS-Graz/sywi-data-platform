# syntax=docker/dockerfile:1.7

ARG DHI_PYTHON_TAG=3.14-debian13
ARG DHI_UV_TAG=0-debian13

FROM dhi.io/uv:${DHI_UV_TAG} AS uv

FROM dhi.io/python:${DHI_PYTHON_TAG}-dev AS builder

COPY --from=uv /usr/local/bin/uv /usr/local/bin/uvx /usr/local/bin/
WORKDIR /opt/dagster/app
ENV UV_PROJECT_ENVIRONMENT=/opt/dagster/venv
ENV VIRTUAL_ENV=${UV_PROJECT_ENVIRONMENT}
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN python -m venv "${VIRTUAL_ENV}"

# Install dependencies (cached layer)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

COPY sywi-core/ /opt/dagster/sywi-core/

# Copy project files
COPY __name__/ /opt/dagster/app/

# Install the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

FROM dhi.io/python:${DHI_PYTHON_TAG} AS runtime

WORKDIR /opt/dagster/app
ENV VIRTUAL_ENV=/opt/dagster/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY --from=builder --chown=65532:65532 /opt/dagster/venv /opt/dagster/venv
COPY --from=builder --chown=65532:65532 /opt/dagster/sywi-core /opt/dagster/sywi-core
COPY --from=builder --chown=65532:65532 /opt/dagster/app /opt/dagster/app

CMD ["dagster", "api", "grpc", "-h", "0.0.0.0", "-p", "4000", "-m", "__name__.definitions"]
