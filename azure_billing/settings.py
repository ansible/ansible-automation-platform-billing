"""
Django settings for project.
"""

from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "w+)ziyx0hm0rv5mxkaw%p@ffjmvyesy$a&bmh!kx_24iu=#7jf"

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
The following settings are expected to be defined there
"""

DATABASES = {}

MANAGED_RESOURCE_GROUP = ""

sys.path.append('/etc/billing')
from billingconf import *