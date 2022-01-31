#!/usr/bin/python3

from azure_billing.azure import azapi
from django.conf import settings

import argparse
import django
import logging
import os

logger = logging.getLogger()


def processArgs():
    parser = argparse.ArgumentParser(
        description="Ansible Automation Platform Azure billing connector",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-d", action="store_true", dest="debugmode", help="Enable debug output"
    )
    return parser.parse_args()


# Main
def main():
    args = processArgs()
    logging.basicConfig(
        level=logging.DEBUG if args.debugmode else logging.INFO,
        format="%(levelname)s %(asctime)s\t%(message)s",
    )

    # Bootstrap django (orm only)
    os.environ["DJANGO_SETTINGS_MODULE"] = "azure_billing.settings"
    django.setup()
    from azure_billing.db import db  # noqa: E402 - Must follow django setup

    logger.info("Checking for unbilled hosts.")
    unbilled = db.getUnbilledHosts()

    if unbilled:
        logger.info(
            "%d unbilled hosts found, sending billing data to Azure"
            % len(unbilled)
        )

        billing_record = azapi.pegBillingCounter(settings.DIMENSION, len(unbilled))
        billing_record["hosts"] = unbilled
        billing_record["dimension"] = settings.DIMENSION

        # Record billing data
        db.recordBillingInstance(billing_record)

        # Mark hosts as billed if successful
        logger.info("Marking hosts as billed/recorded.")
        db.markHostsBilled(unbilled)
    else:
        logger.info("No unbilled hosts found.")


if __name__ == "__main__":
    main()
