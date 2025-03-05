#!/usr/bin/python3
import argparse
import logging
import os
import sys

import django
from django.conf import settings

from aap_billing import BILLING_INTERFACE_AWS
from aap_billing.aws import awsapi
from aap_billing.azure import azapi

logger = logging.getLogger()

version = "v0.3.0"


def processArgs():
    parser = argparse.ArgumentParser(
        description="Ansible Automation Platform billing connector",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-d", action="store_true", dest="debugmode", help="Enable debug output")
    return parser.parse_args()


def get_plan():
    plan_id = settings.PLAN_ID
    if plan_id is None:
        logging.fatal("Missing PLAN_ID in settings file, exiting")
    return plan_id


def determineBaseQuantity():
    if "db" not in sys.modules:
        from aap_billing.db import db  # noqa: E402 - For unit test purposes

    try:
        settings_base_quantity = int(settings.INCLUDED_NODES)
    except (ValueError, TypeError):
        settings_base_quantity = settings.INCLUDED_NODES

    if settings_base_quantity is None:
        logging.fatal("Missing INCLUDED_NODES in settings file, exiting")
        sys.exit(1)

    base_quantity = db.getBaseQuantity()

    if base_quantity is None or base_quantity != settings_base_quantity:
        base_quantity = settings_base_quantity
        db.recordBaseQuantity(base_quantity)

    return base_quantity


# Main
def main():
    args = processArgs()
    logging.basicConfig(
        level=logging.DEBUG if args.debugmode else logging.INFO,
        format="%(levelname)s %(asctime)s\t%(message)s",
    )

    # Print version
    logging.info("Billing version: %s" % version)

    # Bootstrap django (orm only)
    os.environ["DJANGO_SETTINGS_MODULE"] = "aap_billing.settings"
    django.setup()
    from aap_billing.db import db  # noqa: E402 - Must follow django setup

    # Also ensures DB has not gone into Read-Only mode (happens when full)
    db.recordLastRunDateTime()

    db.rolloverIfNeeded()

    logger.info("Checking for newly encountered hosts.")
    (period_start, _) = db.calcBillingPeriod()
    unbilled = db.getUnbilledHosts(period_start)

    if unbilled:
        if BILLING_INTERFACE_AWS == settings.BILLING_INTERFACE:
            logger.info("%d unbilled hosts found, sending billing data to Metering Service" % len(unbilled))
            billing_record = awsapi.pegBillingCounter(settings.DIMENSION, unbilled)

            # Record billing data
            db.recordBillingInstance(billing_record)

            # Mark hosts as billed if successful
            logger.info("Marking hosts as billed/recorded.")
            db.markHostsBilled(unbilled)
        else:
            # Azure
            plan_id = get_plan()

            base_quantity = determineBaseQuantity()
            logging.debug("Base quantity is [%d]" % (base_quantity))

            (hosts_to_bill, hosts_to_mark) = db.getHostsToBill(period_start, base_quantity)
            if len(hosts_to_bill) > 0:
                logger.info("Executed hosts exceed base quantity, sending billing data to Metering Service")
                billing_record = azapi.pegBillingCounter(plan_id, settings.DIMENSION, hosts_to_bill)

                # Record billing data
                db.recordBillingInstance(billing_record)
                logger.info("Marking hosts as billed")
                db.markHostsBilled(hosts_to_bill)

            if len(hosts_to_mark) > 0:
                # Mark as seen, but not billed
                logger.info("Marking hosts as recorded.")
                db.markHostsSeen(hosts_to_mark)
    else:
        logger.info("No new hosts to bill.")


if __name__ == "__main__":
    main()
