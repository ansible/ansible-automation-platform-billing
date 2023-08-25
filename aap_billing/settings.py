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

WELCOME_SERVICE_NAME = "welcome-page-api-svc"
WELCOME_SERVICE_NS = "ansible-automation-platform-welcome"
WELCOME_SERVICE_PORT = "8080"

"""
Import /etc/billing/billingconf.py settings file if it exists.
Required:
DATABASES, (awx and default (billing) db definitions)
PLAN_CONFIG_URL, points to config file containing offer and plan base
                 quantity details
PLAN_STORAGE_TOKEN, used to fetch config file from PLAN_CONFIG_URL
Optional:
WELCOME_SERVICE_NAME,
WELCOME_SERVICE_NS,
WELCOME_SERVICE_PORT, These can be used to override defaults if needed
"""

DATABASES = {}

sys.path.append("/etc/billing")
try:
    from billingconf import *  # noqa
except:  # noqa
    logger.error("Unable to find settings file /etc/billing/billingconf.py")
