"""
Django (test) settings for project.
"""
from django.core.management.utils import get_random_secret_key

import logging
from pathlib import Path
import os

logger = logging.getLogger()

BASE_DIR = Path(__file__).resolve().parent.parent

if os.path.exists("/etc/billing/SECRET_KEY"):
    SECRET_KEY = open("/etc/billing/SECRET_KEY", "r").read().strip()
else:
    SECRET_KEY = get_random_secret_key()

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    "aap_billing.main",
    "aap_billing.billing",
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DATABASE_ROUTERS = ["aap_billing.db.testRouter.TestRouter"]

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True

"""
Dimension name/meter under which to report active
host counts.
"""
DIMENSION = "managed_active_node"

PLAN_CONFIG_URL = "https://rhaap.blob.core.windows.net/billing/plans.json"

# Test databases
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "azurebilling.sqlite3",
    }
}
