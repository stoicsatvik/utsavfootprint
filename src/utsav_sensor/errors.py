"""Explicit data-integrity errors for immutable observation identities."""


class ObservationConflictError(ValueError):
    """An existing observation ID was reused with different evidence."""
