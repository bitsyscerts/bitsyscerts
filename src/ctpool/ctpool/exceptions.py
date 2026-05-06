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


class DatabaseError(CtPoolError):
    """Raised when a database operation fails unexpectedly."""


class DiskGuardError(CtPoolError):
    """Raised when disk space falls below a configured threshold."""


class RateLimitError(FetchError):
    """Raised when a CT log responds with HTTP 429 Too Many Requests."""


class ConfigurationError(CtPoolError):
    """Raised when required configuration is missing or invalid."""


class DispatcherError(CtPoolError):
    """Raised when the dispatcher cannot claim or advance a work unit."""
