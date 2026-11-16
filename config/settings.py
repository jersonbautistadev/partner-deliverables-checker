import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get("DJANGO_DEBUG", "0" if os.environ.get("VERCEL") else "1") == "1"
if os.environ.get("VERCEL_ENV") == "production" and DEBUG:
    raise ImproperlyConfigured("Vercel production must use DJANGO_DEBUG=0.")
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "development-only-never-use-in-production")
if not DEBUG and (len(SECRET_KEY) < 50 or SECRET_KEY.startswith("development-")):
    raise ImproperlyConfigured("Set a random DJANGO_SECRET_KEY of at least 50 characters.")
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")
CSRF_TRUSTED_ORIGINS = list(filter(None, os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")))
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "checker",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "checker.middleware.WorkspaceMiddleware",
    "checker.middleware.ThrottleMiddleware",
    "checker.middleware.PrivateResponsesMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "checker.context.team_context",
            ]
        },
    }
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DJANGO_SQLITE_PATH", BASE_DIR / "db.sqlite3"),
    }
}
if os.environ.get("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": os.environ["POSTGRES_HOST"],
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "NAME": os.environ.get("POSTGRES_DB", "deliverables"),
            "USER": os.environ.get("POSTGRES_USER", "deliverables"),
            "PASSWORD": os.environ["POSTGRES_PASSWORD"],
            "CONN_MAX_AGE": 60,
        }
    }
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
# Private files are intentionally outside STATIC_ROOT. No media URL is registered.
MEDIA_ROOT = Path(os.environ.get("PRIVATE_UPLOAD_ROOT", BASE_DIR / "private_uploads"))
FILE_UPLOAD_PERMISSIONS = 0o600
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o700
DATA_UPLOAD_MAX_MEMORY_SIZE = 256 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FILES = 1
FILE_UPLOAD_HANDLERS = [
    "checker.uploads.BoundedUploadHandler",
    "django.core.files.uploadhandler.MemoryFileUploadHandler",
    "django.core.files.uploadhandler.TemporaryFileUploadHandler",
]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Only enable behind the included proxy, which overwrites this header.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Public-account mail is queued in PostgreSQL; request timing does not depend on SMTP.
EMAIL_BACKEND = "checker.mail.QueueBackend"
DELIVERY_EMAIL_BACKEND = os.environ.get(
    "DELIVERY_EMAIL_BACKEND",
    "django.core.mail.backends.filebased.EmailBackend"
    if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_FILE_PATH = BASE_DIR / ".local-mail"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "0") == "1"
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@localhost")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
PASSWORD_RESET_TIMEOUT = 3600
VERIFICATION_HOURS = 24
INVITATION_HOURS = 48
SESSION_COOKIE_AGE = 86400
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
AUTH_RATE_LIMIT = int(os.environ.get("AUTH_RATE_LIMIT", "10"))
WORK_RATE_LIMIT = int(os.environ.get("WORK_RATE_LIMIT", "60"))
TRUST_PROXY_HEADERS = os.environ.get("TRUST_PROXY_HEADERS", "0") == "1"
MAX_CREATED_WORKSPACES = int(os.environ.get("MAX_CREATED_WORKSPACES", "3"))
MAX_USER_MEMBERSHIPS = int(os.environ.get("MAX_USER_MEMBERSHIPS", "20"))
MAX_WORKSPACE_MEMBERS = int(os.environ.get("MAX_WORKSPACE_MEMBERS", "20"))
MAX_PENDING_INVITATIONS = int(os.environ.get("MAX_PENDING_INVITATIONS", "20"))
WORKSPACE_STORAGE_BYTES = int(os.environ.get("WORKSPACE_STORAGE_BYTES", str(100 * 1024 * 1024)))
MAX_PARTNERS = int(os.environ.get("MAX_PARTNERS", "50"))
MAX_PACKAGES = int(os.environ.get("MAX_PACKAGES", "200"))
MAX_REQUIREMENTS = int(os.environ.get("MAX_REQUIREMENTS", "500"))
MAX_UPLOADS_PER_HOUR = int(os.environ.get("MAX_UPLOADS_PER_HOUR", "60"))
UPLOAD_MAX_BYTES = int(
    os.environ.get(
        "UPLOAD_MAX_BYTES", str(3 * 1024 * 1024 if os.environ.get("VERCEL") else 5 * 1024 * 1024)
    )
)
MAIL_MAX_ATTEMPTS = 6
MAIL_HEALTH_MAX_AGE_SECONDS = max(60, int(os.environ.get("MAIL_HEALTH_MAX_AGE_SECONDS", "900")))
OPS_SECRET = os.environ.get("OPS_SECRET", "")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"safe_request": {"()": "checker.logging.SafeRequestFilter"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
        "safe_request": {"class": "logging.StreamHandler", "filters": ["safe_request"]},
    },
    "loggers": {
        "checker": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["safe_request"], "level": "WARNING", "propagate": False},
    },
}

# Vercel functions use remote PostgreSQL and private object storage.
if os.environ.get("DATABASE_URL"):
    import dj_database_url

    DATABASES = {
        "default": dj_database_url.parse(
            os.environ["DATABASE_URL"],
            conn_max_age=0,
        )
    }
    database_options = DATABASES["default"].setdefault("OPTIONS", {})
    if os.environ.get("DATABASE_REQUIRE_SSL", "1") == "1" and database_options.get(
        "sslmode"
    ) not in {"require", "verify-ca", "verify-full"}:
        database_options["sslmode"] = "require"
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
    database_options.update(connect_timeout=10, prepare_threshold=None)
    if os.environ.get("DATABASE_SSL_ROOT_CERT"):
        database_options["sslrootcert"] = str(BASE_DIR / os.environ["DATABASE_SSL_ROOT_CERT"])
if os.environ.get("PRIVATE_S3_BUCKET"):
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": os.environ["PRIVATE_S3_BUCKET"],
            "access_key": os.environ.get("PRIVATE_S3_ACCESS_KEY"),
            "secret_key": os.environ.get("PRIVATE_S3_SECRET_KEY"),
            "endpoint_url": os.environ.get("PRIVATE_S3_ENDPOINT_URL") or None,
            "region_name": os.environ.get("PRIVATE_S3_REGION", "us-east-1"),
            "location": os.environ.get("PRIVATE_S3_PREFIX", "originals"),
            "default_acl": None,
            "querystring_auth": True,
            "querystring_expire": 60,
            "file_overwrite": False,
            "custom_domain": None,
            "signature_version": "s3v4",
            "addressing_style": os.environ.get("PRIVATE_S3_ADDRESSING_STYLE", "auto"),
            "object_parameters": {"CacheControl": "private, no-store"},
        },
    }
if os.environ.get("VERCEL"):
    # Vercel's proxy, rather than the local Compose proxy, terminates TLS.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    if UPLOAD_MAX_BYTES > 3 * 1024 * 1024:
        raise ImproperlyConfigured(
            "Vercel upload limit must be at most 3 MiB, leaving room for multipart encoding."
        )

CSRF_FAILURE_VIEW = "checker.accounts.csrf_failure"

# A serverless deployment must never silently fall back to ephemeral SQLite/files.
if not DEBUG and os.environ.get("VERCEL"):
    if not os.environ.get("DATABASE_URL") or not os.environ.get("PRIVATE_S3_BUCKET"):
        raise ImproperlyConfigured("Vercel production requires DATABASE_URL and PRIVATE_S3_BUCKET.")
