"""
Django settings for project.
"""

from django.core.management.utils import get_random_secret_key
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
    "aap_billing.main",
    "aap_billing.billing",
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DATABASE_ROUTERS = ["aap_billing.db.db.BillingRouter"]

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

"""
Import /etc/billing/billingconf.py settings file if it exists.
Database settings are expected to be defined there.
"""

DATABASES = {}

sys.path.append("/etc/billing")
try:
    from billingconf import *  # noqa
except:  # noqa
    logger.error("Unable to find settings file /etc/billing/billingconf.py")
