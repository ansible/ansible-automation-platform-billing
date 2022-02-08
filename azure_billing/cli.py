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

    logger.info("Calculating/validating billing period.")
    rollover_date = db.getRolloverDate()
    logger.info(
        "Billing period rollover date: %s" % rollover_date.strftime("%m-%d-%Y")
    )

    logger.info("Checking for unbilled hosts.")
    unbilled = db.getUnbilledHosts(rollover_date)

    if unbilled:
        logger.info(
            "%d unbilled hosts found, sending billing data to Azure"
            % len(unbilled)
        )

        billing_record = azapi.pegBillingCounter(settings.DIMENSION, unbilled)

        # Record billing data
        db.recordBillingInstance(billing_record)

        # Mark hosts as billed if successful
        logger.info("Marking hosts as billed/recorded.")
        db.markHostsBilled(unbilled)
    else:
        logger.info("No unbilled hosts found.")

    # Rollover to new billing period if needed
    logger.info("Checking for billing period rollover.")
    if db.checkRolloverNeeded(rollover_date):
        logger.info("Rolling over to new billing period.")
        db.rollover()


if __name__ == "__main__":
    main()
