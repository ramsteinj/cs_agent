"""Django settings for cs_agent.

All environment-specific values are read from environment variables / backend/.env
(see .env.example and specs/08-dev-and-testing.md).
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "common",
    "accounts",
    "knowledge",
    "chat",
    "settings_app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": env.db("DATABASE_URL")}

# Must be set before the first migrate (specs/03-data-model.md).
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.TokenAuthentication"],
    # Admin-only by default; public endpoints opt in with AllowAny (specs/07-security.md).
    "DEFAULT_PERMISSION_CLASSES": ["common.permissions.IsAdminRole"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_PAGINATION_CLASS": "common.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "common.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_RATES": {"login": "10/min"},
}

# Fernet key used to encrypt the Anthropic API Key in the DB (specs/07-security.md §3).
# Validated at startup by settings_app (missing/invalid -> ImproperlyConfigured).
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", default="")

# RAG / embeddings (specs/05-rag-pipeline.md). EMBEDDING_DIM must match the migration.
EMBEDDING_BACKEND = env("EMBEDDING_BACKEND", default="sentence_transformers")  # or "fake"
EMBEDDING_MODEL = env("EMBEDDING_MODEL", default="intfloat/multilingual-e5-small")
EMBEDDING_DIM = env.int("EMBEDDING_DIM", default=384)
RAG_TOP_K = env.int("RAG_TOP_K", default=5)
RAG_MAX_DISTANCE = env.float("RAG_MAX_DISTANCE", default=0.6)
CHUNK_MAX_CHARS = 500
CHUNK_OVERLAP_CHARS = 100

# Login lockout policy (specs/07-security.md §2)
LOGIN_MAX_FAILED_ATTEMPTS = 5
LOGIN_LOCK_MINUTES = 5

# Default admin created when no ADMIN user exists (specs/01 F-A2)
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin1234!"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "accounts": {"handlers": ["console"], "level": "INFO"},
        "settings_app": {"handlers": ["console"], "level": "INFO"},
        "knowledge": {"handlers": ["console"], "level": "INFO"},
    },
}
