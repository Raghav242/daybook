class NotFound(Exception):
    pass


class Conflict(Exception):
    """The request is valid but conflicts with the current state of the records."""


class Invalid(Exception):
    """The request is well formed but refers to something it may not use."""
