from django.conf import settings
import logging
import requests

logger = logging.getLogger()


def update_welcome_page(data):
    url = f"{settings.WELCOME_SERVICE_NAME}.{settings.WELCOME_SERVICE_NS}.svc.cluster.local:{settings.WELCOME_SERVICE_PORT}"
    try:
        r = requests.post(url, json=data)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"Error while attempting to update welcome page usage data: {e}")
