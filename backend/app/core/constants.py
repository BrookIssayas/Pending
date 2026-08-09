class EnvVars:
    """Environmental variable names"""

    # Core Settings
    SUPABASE_URL = "SUPABASE_URL"
    SUPABASE_KEY = "SUPABASE_KEY"
    SUPABASE_JWT_SECRET = "SUPABASE_JWT_SECRET"


class Defaults:
    """Default configuration values"""

    # Application Metadata
    APP_NAME = "Job Tracker"
    APP_VERSION = "1.0.0"
    APP_DESCRIPTION = "Easy, accessible job-tracker service."

    # API Configuration
    API_V1_STR = "/api/v1"

    # CORS
    CORS_ORIGINS = ["*"]

    # Logging
    LOG_LEVEL = "INFO"


class Validation:
    """Validation rules and constraints"""

    # Password requirements
    MIN_PASSWORD_LENGTH = 8


class Supabase:
    """Supabase-specific Constants"""

    # Secret Names for GSM
    REQUIRED_SECRETS = ["SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_JWT_SECRET"]

    # User Metadata Fields
    FULL_NAME_FIELD = "full_name"

    # GSM Secret Path Template
    SECRET_PATH_TEMPLATE = "projects/{project_id}/secrets/{secret_name}/versions/latest"


class OAuth:
    """OAuth-specific Constants"""

    GOOGLE = "google"