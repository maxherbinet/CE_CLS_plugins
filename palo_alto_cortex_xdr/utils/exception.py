"""Palo Alto Cortex XDR Plugin Exceptions."""


class CortexXDRException(Exception):
    """Custom exception for Palo Alto Cortex XDR plugin errors."""

    pass


class MappingValidationError(Exception):
    """Exception raised when the mapping file fails validation."""

    pass
