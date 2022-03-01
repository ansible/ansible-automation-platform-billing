#!/usr/bin/python3

from aap_billing.azure import azapi
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
    os.environ["DJANGO_SETTINGS_MODULE"] = "aap_billing.settings"
    django.setup()
    from aap_billing.db import db  # noqa: E402 - Must follow django setup

    db.rolloverIfNeeded()

    logger.info("Checking for unbilled hosts.")
    (period_start, _) = db.calcBillingPeriod()
    unbilled = db.getUnbilledHosts(period_start)

    if unbilled:
        logger.info(
            "%d unbilled hosts found, sending billing data to Metering Service"
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


if __name__ == "__main__":
    main()
