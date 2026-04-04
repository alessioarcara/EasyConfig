class EasyConfigError(Exception):
    """Base class for all ezconfy library errors."""


class SchemaError(EasyConfigError):
    """Raised when a schema YAML is malformed or contains invalid types."""


class InstantiationError(EasyConfigError):
    """Raised when object instantiation or configuration validation fails."""
