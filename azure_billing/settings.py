"""
Django settings for project.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "w+)ziyx0hm0rv5mxkaw%p@ffjmvyesy$a&bmh!kx_24iu=#7jf"

ALLOWED_HOSTS = []

INSTALLED_APPS = ["main", "billing"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DATABASE_ROUTERS = ["db.db.BillingRouter"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "azurebilling",
        "USER": "<user>",
        "PASSWORD": "<passwd>",
        "HOST": "<dbhost>",
        "PORT": "5432",
    },
    "awx": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "awx",
        "USER": "<user>",
        "PASSWORD": "<passwd>",
        "HOST": "<dbhost>",
        "PORT": "5432",
    },
}

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True
