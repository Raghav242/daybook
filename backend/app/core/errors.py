class NotFound(Exception):
    pass


class Conflict(Exception):
    """The request is valid but conflicts with the current state of the records."""
