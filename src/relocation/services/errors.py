"""Domain errors raised by the service layer; the API maps them to HTTP status codes."""


class NotFound(LookupError):
    """A referenced record does not exist (HTTP 404)."""


class ValidationFailed(ValueError):
    """The write breaks a data rule (HTTP 422)."""
