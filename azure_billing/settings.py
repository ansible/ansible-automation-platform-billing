"""
Django settings for project.
"""

from django.core.management.utils import get_random_secret_key
from pathlib import Path
import os
import sys

BASE_DIR = Path(__file__).resolve().parent.parent

if os.path.exists("/etc/billing/SECRET_KEY"):
    SECRET_KEY = open("/etc/billing/SECRET_KEY", "r").read().strip()
else:
    SECRET_KEY = get_random_secret_key()

ALLOWED_HOSTS = []

INSTALLED_APPS = ["azure_billing.main", "azure_billing.billing"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DATABASE_ROUTERS = ["azure_billing.db.db.BillingRouter"]

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True

"""
Import /etc/billing/billingconf.py settings file if it exists.
Database settings are expected to be defined there
"""

DATABASES = {}

sys.path.append("/etc/billing")
from billingconf import *  # noqa
