# Build-time version injected by CI (see .github/scripts/gen-version.sh).
# Docker tags forbid '+', so the Docker variant uses '-' as separator.
ARG BUILD_VERSION=0.0.0+dev

# ── Stage 1: build wheels for both packages ──────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build tooling
RUN pip install --no-cache-dir hatchling

# Copy and build ctpool first (certsapi depends on it)
COPY src/ctpool /build/ctpool
RUN pip wheel --no-cache-dir --wheel-dir /wheels /build/ctpool

# Copy and build certsapi, replacing the file:// dep with the wheel we just built
COPY src/api /build/api
# Rewrite the local file reference so pip can resolve it from the wheel dir
RUN sed 's|ctpool @ file://[^"]*|ctpool|g' /build/api/pyproject.toml \
    > /build/api/pyproject_ci.toml \
    && mv /build/api/pyproject_ci.toml /build/api/pyproject.toml
RUN pip wheel --no-cache-dir --wheel-dir /wheels --find-links /wheels /build/api

# ── Stage 2: lean runtime image ───────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Non-root user for security
RUN useradd --system --no-create-home appuser

WORKDIR /app

# Install both wheels and all their dependencies
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links /wheels ctpool certsapi \
    && rm -rf /wheels

# Copy alembic config so migrations can be run from this image
COPY src/ctpool/alembic.ini /app/alembic.ini
COPY src/ctpool/migrations   /app/migrations

USER appuser

# Propagate the build version into the runtime environment so that
# certsapi.__version__ and ctpool.__version__ can read it.
ARG BUILD_VERSION
ENV BUILD_VERSION="${BUILD_VERSION}"

LABEL org.opencontainers.image.title="bitsyscerts-api" \
      org.opencontainers.image.version="${BUILD_VERSION}"

# Default: run the API server.  Override CMD in compose for ctpool workers.
CMD ["certsapi", "serve", "--workers", "2"]
