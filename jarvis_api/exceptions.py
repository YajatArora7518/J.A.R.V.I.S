# jarvis_api/exceptions.py
# Custom Exception Hierarchy for JARVIS API & SDK

class JarvisError(Exception):
    """Base exception for all JARVIS errors."""
    pass


class AuthenticationError(JarvisError):
    """Raised when API key or authentication verification fails."""
    pass


class ToolNotFoundError(JarvisError):
    """Raised when a requested tool is not registered in ToolRegistry."""
    pass


class ValidationError(JarvisError):
    """Raised when parameter validation fails."""
    pass


class SecurityError(JarvisError):
    """Raised when an operation is blocked by SecurityManager policies."""
    pass


class ExecutionError(JarvisError):
    """Raised when a tool execution fails at runtime."""
    pass


class TimeoutError(JarvisError):
    """Raised when an operation exceeds its configured execution timeout."""
    pass


class APIConnectionError(JarvisError):
    """Raised when network or API connection to AI provider fails."""
    pass


class ConfigurationError(JarvisError):
    """Raised when system or model configuration is missing or invalid."""
    pass
