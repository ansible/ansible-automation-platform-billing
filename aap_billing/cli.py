#!/usr/bin/python3
from aap_billing import BILLING_INTERFACE_AWS
from aap_billing.azure import azapi
from aap_billing.aws import awsapi
from django.conf import settings

import argparse
import django
import logging
import os

logger = logging.getLogger()


def processArgs():
    parser = argparse.ArgumentParser(
        description="Ansible Automation Platform billing connector",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-d", action="store_true", dest="debugmode", help="Enable debug output")
    return parser.parse_args()


# Main
def main():
    args = processArgs()
    logging.basicConfig(
        level=logging.DEBUG if args.debugmode else logging.INFO,
        format="%(levelname)s %(asctime)s\t%(message)s",
    )

    # Bootstrap django (orm only)
    os.environ["DJANGO_SETTINGS_MODULE"] = "aap_billing.settings"
    django.setup()
    from aap_billing.db import db  # noqa: E402 - Must follow django setup

    # Also ensures DB has not gone into Read-Only mode (happens when full)
    db.recordLastRunDateTime()

    db.rolloverIfNeeded()

    logger.info("Checking for unbilled hosts.")
    (period_start, _) = db.calcBillingPeriod()
    unbilled = db.getUnbilledHosts(period_start)

    if unbilled:
        logger.info("%d unbilled hosts found, sending billing data to Metering Service" % len(unbilled))

        if BILLING_INTERFACE_AWS == settings.BILLING_INTERFACE:
            billing_record = awsapi.pegBillingCounter(settings.DIMENSION, unbilled)
        else:
            billing_record = azapi.pegBillingCounter(settings.DIMENSION, unbilled)

        # Record billing data
        db.recordBillingInstance(billing_record)

        # Mark hosts as billed if successful
        logger.info("Marking hosts as billed/recorded.")
        db.markHostsBilled(unbilled)
    else:
        logger.info("No unbilled hosts found.")


if __name__ == "__main__":
    main()
