"""Domain exception hierarchy for ctpool.

All exceptions raised by ctpool business logic inherit from CtPoolError
so callers can catch the whole domain with a single except clause.
"""


class CtPoolError(Exception):
    """Base class for all ctpool domain exceptions."""


class FetchError(CtPoolError):
    """Raised when an HTTP request to a CT log fails."""


class ParseError(CtPoolError):
    """Raised when a CT log entry cannot be decoded or parsed."""


class UnsupportedEntryTypeError(ParseError):
    """Raised when a CT log entry has an unknown or unsupported entry type.

    Subclass of :class:`ParseError` so existing callers that catch ``ParseError``
    continue to work, while workers that want to distinguish unsupported-type
    entries from genuine parse failures can catch this class first.
    """


class DatabaseError(CtPoolError):
    """Raised when a database operation fails unexpectedly."""


class DiskGuardError(CtPoolError):
    """Raised when disk space falls below a configured threshold."""


class RateLimitError(FetchError):
    """Raised when a CT log responds with HTTP 429 Too Many Requests."""

    def __init__(self, message: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds: int | None = retry_after_seconds


class ConfigurationError(CtPoolError):
    """Raised when required configuration is missing or invalid."""


class DispatcherError(CtPoolError):
    """Raised when the dispatcher cannot claim or advance a work unit."""


class SchemaStateError(CtPoolError):
    """Raised when Alembic revision state does not match the actual schema."""


class DatabaseInitError(CtPoolError):
    """Raised when init-db cannot safely prepare the target database."""


class DatabasePrivilegeError(DatabaseInitError):
    """Raised when maintenance DB privileges are insufficient for init-db."""
