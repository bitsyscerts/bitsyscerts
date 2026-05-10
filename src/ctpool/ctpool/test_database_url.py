"""Resolve a safe integration-test database URL from the runtime environment."""

from __future__ import annotations

from sqlalchemy.engine import URL, make_url

TEST_DATABASE_URL_ENV = "BITSYSCERTS_TEST_DATABASE_URL"
_TEST_DATABASE_SUFFIX = "_test"


def resolve_test_database_url(
    *,
    source_database_url: str | None,
    explicit_test_database_url: str | None,
    fallback_database_url: str,
) -> str:
    """Return the isolated database URL used by integration tests.

    Preference order:
    1. ``BITSYSCERTS_TEST_DATABASE_URL`` when explicitly provided.
    2. A URL derived from ``source_database_url`` with the database name
       rewritten to ``<name>_test``.
    3. ``fallback_database_url`` when no runtime database URL exists.

    Raises:
        RuntimeError: When the resolved test URL points at the same non-test
            database as ``source_database_url``.
    """
    source_url = make_url(source_database_url) if source_database_url else None

    if explicit_test_database_url:
        resolved_url = make_url(explicit_test_database_url)
    elif source_url is not None:
        resolved_url = _derive_test_database_url(source_url)
    else:
        resolved_url = make_url(fallback_database_url)

    _validate_test_database_url(source_url=source_url, test_url=resolved_url)
    return rendered_url(resolved_url)


def rendered_url(url: URL) -> str:
    """Render a SQLAlchemy URL with credentials intact for engine creation."""
    return url.render_as_string(hide_password=False)


def _derive_test_database_url(source_url: URL) -> URL:
    database_name = source_url.database
    if not database_name:
        raise RuntimeError("DATABASE_URL must include a database name for tests.")
    if database_name.endswith(_TEST_DATABASE_SUFFIX):
        return source_url
    return source_url.set(database=f"{database_name}{_TEST_DATABASE_SUFFIX}")


def _validate_test_database_url(*, source_url: URL | None, test_url: URL) -> None:
    if not test_url.database:
        raise RuntimeError(
            "Integration test database URL must include a database name."
        )
    if source_url is None:
        return
    same_database = (
        source_url.host == test_url.host
        and source_url.port == test_url.port
        and source_url.database == test_url.database
    )
    if same_database and not test_url.database.endswith(_TEST_DATABASE_SUFFIX):
        raise RuntimeError(
            "Refusing to run integration tests against the live DATABASE_URL "
            f"database '{test_url.database}'. Set {TEST_DATABASE_URL_ENV} to a "
            "dedicated test database or use a DATABASE_URL that already points "
            "at a *_test database."
        )
