"""
Django settings for project.
"""
from datetime import datetime
from django.core.management.utils import get_random_secret_key
from django.utils import timezone
import logging
from pathlib import Path
import os
import sys

logger = logging.getLogger()

BASE_DIR = Path(__file__).resolve().parent.parent

if os.path.exists("/etc/billing/SECRET_KEY"):
    SECRET_KEY = open("/etc/billing/SECRET_KEY", "r").read().strip()
else:
    SECRET_KEY = get_random_secret_key()

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "constance",
    "azure_billing.main",
    "azure_billing.billing",
    "constance.backends.database",
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DATABASE_ROUTERS = ["azure_billing.db.db.BillingRouter"]

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True

CONSTANCE_BACKEND = "constance.backends.database.DatabaseBackend"

CONSTANCE_DBS = "billing"

CONSTANCE_CONFIG = {
    "INSTALL_DATE": (
        datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ),
        "Installation date",
        datetime,
    ),
    "BILLING_PERIOD_START": (None, "Billing period start date", datetime),
    "BILLING_PERIOD_END": (None, "Billing period end date", datetime),
}


"""
Dimension name/meter under which to report active
host counts.
"""
DIMENSION = "managed_active_node"

"""
Import /etc/billing/billingconf.py settings file if it exists.
Database settings are expected to be defined there
"""

DATABASES = {}

sys.path.append("/etc/billing")
try:
    from billingconf import *  # noqa
except:  # noqa
    logger.error("Unable to find settings file /etc/billing/billingconf.py")
