#!/usr/bin/python3
from aap_billing import BILLING_INTERFACE_AWS, BILLING_INTERFACE_AZURE
from aap_billing.azure import azapi, storage
from aap_billing.aws import awsapi
from aap_billing.welcome import client
from django.conf import settings

import argparse
import django
import logging
import os
import sys

logger = logging.getLogger()

version = "v0.2.9"


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


def exitIfNotMarketplaceDeployment(metadata):
    if metadata["kind"] != "MarketPlace":
        logger.info(
            """
            Billing is not active/functional in single tenant deployments
            """
        )
        sys.exit(0)
    if "resource_id" not in metadata:
        logger.error(
            """
            No billing details present on managed app metadata.
            Check offer/plan billing configuration.  If billing
            is configured properly, report this error.
            """
        )
        sys.exit(1)


def update_welcome_page_usage(db, period_start, period_end, base_quantity):
    logger.info("Updating welcome page usage data.")
    data = {"periodstart": period_start, "periodend": period_end, "used": db.getProcessedHostCount(period_start), "included": base_quantity}
    client.update_welcome_page(data)


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
    (period_start, period_end) = db.calcBillingPeriod()
    unbilled = db.getUnbilledHosts(period_start)

    if BILLING_INTERFACE_AZURE == settings.BILLING_INTERFACE:
        # Pre load offer/plan/base quantity info, needed for welcome page
        # Get offer/plan from metadata
        metadata = azapi.getManAppIdAndMetadata()
        # Ensure Marketplace deployment with billing data
        exitIfNotMarketplaceDeployment(metadata)

        offer_id = metadata["offer_id"]
        plan_id = metadata["plan_id"]
        base_quantity = determineBaseQuantity(offer_id, plan_id)
        logging.debug("Base quantity for offer [%s] and plan [%s] is [%d]" % (offer_id, plan_id, base_quantity))

        if hasattr(settings, "WELCOME_API_URL"):
            update_welcome_page_usage(db, period_start, period_end, base_quantity)

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
