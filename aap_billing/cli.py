#!/usr/bin/python3
from aap_billing import BILLING_INTERFACE_AWS
from aap_billing.azure import azapi, storage
from aap_billing.aws import awsapi
from django.conf import settings

import argparse
import django
import logging
import os
import sys

logger = logging.getLogger()

version = "v0.2.5"


def processArgs():
    parser = argparse.ArgumentParser(
        description="Ansible Automation Platform billing connector",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-d", action="store_true", dest="debugmode", help="Enable debug output")
    return parser.parse_args()


def determineBaseQuantity(offer_id, plan_id):
    if "db" not in sys.modules:
        from aap_billing.db import db  # noqa: E402 - For unit test purposes

    base_quantity = db.getBaseQuantity(offer_id, plan_id)
    if base_quantity is None:
        base_quantity = storage.fetchBaseQuantity(settings.PLAN_CONFIG_URL, settings.PLAN_STORAGE_TOKEN, offer_id, plan_id)
        if base_quantity is None:
            logging.fatal("Unable to find base quantity for offer [%s] and plan [%s]" % (offer_id, plan_id))
            sys.exit(1)
        else:
            db.recordBaseQuantity(offer_id, plan_id, base_quantity)
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
            # Get offer/plan from metadata
            metadata = azapi.getManAppIdAndMetadata()
            offer_id = metadata["offer_id"]
            plan_id = metadata["plan_id"]
            base_quantity = determineBaseQuantity(offer_id, plan_id)
            logging.debug("Base quantity for offer [%s] and plan [%s] is [%d]" % (offer_id, plan_id, base_quantity))

            (hosts_to_bill, hosts_to_mark) = db.getHostsToBill(period_start, base_quantity)
            if len(hosts_to_bill) > 0:
                logger.info("Executed hosts exceed base quantity, sending billing data to Metering Service")
                billing_record = azapi.pegBillingCounter(settings.DIMENSION, hosts_to_bill)

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
