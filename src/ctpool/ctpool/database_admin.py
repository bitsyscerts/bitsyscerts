"""Create, drop, and recreate PostgreSQL databases from a maintenance connection."""

from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError

from ctpool.config import Settings
from ctpool.exceptions import DatabaseInitError, DatabasePrivilegeError

_MAINTENANCE_DB = "postgres"
_RESERVED_DATABASES = {"postgres", "template0", "template1"}


def resolve_admin_database_url(settings: Settings) -> str:
    """Return the maintenance DB URL used for create and reset operations."""
    target_url = make_url(str(settings.database_url))
    target_database = _target_database_name(target_url)
    _raise_for_reserved_database(target_database)
    if settings.database_admin_url is not None:
        admin_url = make_url(str(settings.database_admin_url))
        _raise_for_mismatched_server(target_url, admin_url)
        admin_database = _target_database_name(admin_url)
        if admin_database == target_database:
            raise DatabaseInitError(
                "DATABASE_ADMIN_URL must point to a maintenance database, not the "
                "target application database."
            )
        return admin_url.render_as_string(hide_password=False)
    derived_url = target_url.set(database=_MAINTENANCE_DB)
    if _target_database_name(derived_url) == target_database:
        raise DatabaseInitError(
            "DATABASE_URL must not point at the maintenance database when using "
            "init-db."
        )
    return derived_url.render_as_string(hide_password=False)


def database_exists_sync(settings: Settings) -> bool:
    """Return whether the target application database currently exists."""
    target_name = target_database_name(settings)
    try:
        with _admin_engine(settings).connect() as connection:
            result = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
                {"database_name": target_name},
            )
            return result.scalar_one_or_none() == 1
    except SQLAlchemyError as exc:
        raise _build_admin_error(
            exc,
            "Unable to query pg_database via the maintenance connection. Set "
            "DATABASE_ADMIN_URL to a privileged maintenance database user if "
            "DATABASE_URL cannot access the postgres database.",
        ) from exc


def create_database_if_missing_sync(settings: Settings) -> bool:
    """Create the target DB if missing and return whether it was created."""
    if database_exists_sync(settings):
        return False
    target_url = make_url(str(settings.database_url))
    database_name = _quote_identifier(target_database_name(settings))
    owner_name = target_url.username
    statement = f"CREATE DATABASE {database_name}"
    if owner_name:
        statement += f" OWNER {_quote_identifier(owner_name)}"
    try:
        with _admin_engine(settings).connect() as connection:
            connection.exec_driver_sql(statement)
            return True
    except SQLAlchemyError as exc:
        raise _build_admin_error(
            exc,
            "Unable to create the target database. The maintenance connection "
            "must have CREATEDB privileges or DATABASE_ADMIN_URL must point to "
            "a privileged maintenance user.",
        ) from exc


def recreate_database_sync(settings: Settings) -> bool:
    """Drop and recreate the target database; return whether it existed beforehand."""
    target_url = make_url(str(settings.database_url))
    target_name = target_database_name(settings)
    existed = database_exists_sync(settings)
    drop_statement = f"DROP DATABASE IF EXISTS {_quote_identifier(target_name)}"
    create_statement = f"CREATE DATABASE {_quote_identifier(target_name)}"
    if target_url.username:
        create_statement += f" OWNER {_quote_identifier(target_url.username)}"
    try:
        with _admin_engine(settings).connect() as connection:
            if existed:
                connection.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) "
                        "FROM pg_stat_activity "
                        "WHERE datname = :database_name "
                        "AND pid <> pg_backend_pid()"
                    ),
                    {"database_name": target_name},
                )
                connection.exec_driver_sql(drop_statement)
            connection.exec_driver_sql(create_statement)
            return existed
    except SQLAlchemyError as exc:
        raise _build_admin_error(
            exc,
            "Unable to drop and recreate the target database. The maintenance "
            "connection must have sufficient privileges or DATABASE_ADMIN_URL "
            "must point to a privileged maintenance user.",
        ) from exc


def target_database_name(settings: Settings) -> str:
    """Return the application database name from DATABASE_URL."""
    database_name = _target_database_name(make_url(str(settings.database_url)))
    _raise_for_reserved_database(database_name)
    return database_name


def _target_database_name(url: URL) -> str:
    database = url.database
    if not database:
        raise DatabaseInitError("DATABASE_URL must include a database name.")
    return database


def _quote_identifier(identifier: str) -> str:
    return f'"{identifier.replace('"', '""')}"'


def _build_admin_error(exc: SQLAlchemyError, prefix: str) -> DatabasePrivilegeError:
    detail = _extract_sqlalchemy_message(exc)
    return DatabasePrivilegeError(f"{prefix} PostgreSQL reported: {detail}")


def _extract_sqlalchemy_message(exc: SQLAlchemyError) -> str:
    original_error = getattr(exc, "orig", None)
    if original_error is not None:
        return str(original_error)
    return str(exc)


def _raise_for_mismatched_server(target_url: URL, admin_url: URL) -> None:
    if (
        admin_url.drivername != target_url.drivername
        or admin_url.host != target_url.host
        or admin_url.port != target_url.port
    ):
        raise DatabaseInitError(
            "DATABASE_ADMIN_URL must point to the same PostgreSQL server as "
            "DATABASE_URL."
        )


def _raise_for_reserved_database(database_name: str) -> None:
    if database_name in _RESERVED_DATABASES:
        raise DatabaseInitError(
            f"init-db cannot target reserved PostgreSQL database {database_name!r}."
        )


def _admin_engine(settings: Settings):
    return create_engine(
        resolve_admin_database_url(settings),
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )
