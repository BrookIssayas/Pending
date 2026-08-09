class ErrorMessages:
    """Error messages shown to users"""

    INVALID_CREDENTIALS = "Invalid email or password"
    INVALID_TOKEN = "Invalid authentication token"
    INVALID_TOKEN_MISSING_USER = "Invalid token: missing user identification"

    LOGOUT_FAILED = "Failed to log out"
    REGISTRATION_GAILED = "Registration failed"
    AUTHENTICATION_FAILED = "Authentication failed"


class SuccessMessages:
    """Success messages shown to users"""

    LOGOUT_SUCCESS = "Successfully logged out"
    PASSWORD_RESET_SENT = "Password reset email sent"


class LogMessages:
    """Internal log messages"""

    USER_CREATED = "User created: {user_id}"
    USER_LOGGED_IN = "User logged in: {user_id}"
    USER_LOGGED_OUT = "User logged out: {user_id}"

    LOADING_FROM_ENV = "Loading settings form environment variables"

    # JWT Validation
    JWT_MISSING_SUB = "Token is valid but missing 'sub' claim"
    JWT_VALIDATION_FAILED = "JWT validation failed: {error}"