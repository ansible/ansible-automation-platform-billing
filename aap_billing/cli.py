#!/usr/bin/python3
from aap_billing import BILLING_INTERFACE_AWS
from aap_billing.azure import azapi, storage
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

    # Get offer/plan from metadata
    metadata = azapi.getManAppIdAndMetadata()
    offer_id = metadata["offer_id"]
    plan_id = metadata["plan_id"]

    # Check/set plan base quantity
    base_quantity = db.getBaseQuantity(offer_id, plan_id)
    if not base_quantity:
        base_quantity = storage.fetchBaseQuantity(settings.PLAN_CONFIG_URL, offer_id, plan_id)
        if base_quantity:
            db.recordBaseQuantity(offer_id, plan_id, base_quantity)
        else:
            logging.fatal(
                "Unable to find base quantity for offer [%s] and plan [%s].  Please check plans.json file in RHAAP blob storage." % (offer_id, plan_id)
            )
    else:
        logging.debug("Base quantity for offer [%s] and plan [%s] is [%d]" % (offer_id, plan_id, base_quantity))

    logger.info("Checking for newly encountered hosts.")
    (period_start, _) = db.calcBillingPeriod()
    unbilled = db.getUnbilledHosts(period_start)

    # Get number of "seen" hosts to compare to base quantity threshold
    processed_host_count = db.getProcessedHostCount(period_start)
    logger.debug("Current processed host count is [%d]" % processed_host_count)

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

            # If already processed hosts + new ones exceeds base quantity, bill those that exceed base_quantity
            if (processed_host_count + len(unbilled)) > base_quantity:
                number_to_report = processed_host_count + len(unbilled) - base_quantity
                hosts_to_bill = unbilled[0:number_to_report]
                hosts_to_mark = unbilled[number_to_report:]
                logger.info("Executed hosts exceed base quantity, sending billing data to Metering Service")
                billing_record = azapi.pegBillingCounter(settings.DIMENSION, hosts_to_bill)

                # Record billing data
                db.recordBillingInstance(billing_record)

                # Mark hosts as billed if successful
                logger.info("Marking hosts as billed/recorded.")
                db.markHostsBilled(hosts_to_bill)
                db.markHostsBilled(hosts_to_mark, False)
            else:
                # Mark as seen, but not billed
                db.markHostsBilled(unbilled, False)
    else:
        logger.info("No new hosts to bill.")


if __name__ == "__main__":
    main()
