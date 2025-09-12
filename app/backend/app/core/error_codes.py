from enum import Enum

class ErrorCode(str, Enum):
    # --- Generic / HTTP-ish ---
    INTERNAL_ERROR = "internal_error"
    BAD_REQUEST = "bad_request"
    VALIDATION_ERROR = "validation_error"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    RATE_LIMITED = "rate_limited"
    SERVICE_UNAVAILABLE = "service_unavailable"
    TIMEOUT = "timeout"

    # --- Auth / Sessions ---
    EMAIL_ALREADY_REGISTERED = "email_already_registered"
    PHONE_ALREADY_REGISTERED = "phone_already_registered"
    INVALID_CREDENTIALS = "invalid_credentials"
    LOGIN_BLOCKED = "login_blocked"                 # throttle active
    EMAIL_NOT_VERIFIED = "email_not_verified"
    VERIFICATION_CODE_INVALID = "verification_code_invalid"
    VERIFICATION_CODE_EXPIRED = "verification_code_expired"
    VERIFICATION_RESEND_TOO_SOON = "verification_resend_too_soon"
    TOKEN_MISSING = "token_missing"
    TOKEN_INVALID = "token_invalid"
    TOKEN_EXPIRED = "token_expired"
    SESSION_INVALID = "session_invalid"
    SESSION_EXPIRED = "session_expired"
    ADMIN_TOKEN_INVALID = "admin_token_invalid"
    PASSWORD_TOO_WEAK = "password_too_weak"
    PASSWORD_SAME_AS_OLD = "password_same_as_old"
    PASSWORD_RESET_INVALID = "password_reset_invalid"
    PASSWORD_RESET_EXPIRED = "password_reset_expired"
    PASSWORD_RESET_USED = "password_reset_used"

    # --- Users / Admin ---
    USER_NOT_FOUND = "user_not_found"
    USER_UPDATE_FAILED = "user_update_failed"
    USER_BALANCE_TOO_LOW = "user_balance_too_low"

    # --- Bots shop ---
    BOT_NOT_FOUND = "bot_not_found"
    BOT_ALREADY_EXISTS = "bot_already_exists"
    BOT_ACTIVATION_CODE_INVALID = "bot_activation_code_invalid"
    BOT_RATE_INVALID = "bot_rate_invalid"
    BOT_DELETE_FORBIDDEN = "bot_delete_forbidden"     # has instances

    # --- Instances ---
    INSTANCE_NOT_FOUND = "instance_not_found"
    INSTANCE_CREATION_FAILED = "instance_creation_failed"
    INSTANCE_ID_ALREADY_EXISTS = "instance_id_already_exists"
    INSTANCE_CONFIG_INVALID = "instance_config_invalid"
    INSTANCE_ALREADY_ACTIVE = "instance_already_active"
    INSTANCE_ALREADY_PAUSED = "instance_already_paused"
    INSTANCE_NOT_ENOUGH_BALANCE = "instance_not_enough_balance"

    # --- Email / Messaging ---
    EMAIL_SEND_FAILED = "email_send_failed"
    MAIL_TRANSPORT_UNAVAILABLE = "mail_transport_unavailable"

    # --- Infra / Storage / External ---
    DATABASE_ERROR = "database_error"
    UNIQUE_CONSTRAINT_VIOLATION = "unique_constraint_violation"
    REDIS_ERROR = "redis_error"
    EXTERNAL_API_ERROR = "external_api_error"
    EXTERNAL_API_TIMEOUT = "external_api_timeout"
    EXTERNAL_API_UNAUTHORIZED = "external_api_unauthorized"

    # --- Config / Env ---
    CONFIG_ERROR = "config_error"
