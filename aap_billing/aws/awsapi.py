from datetime import datetime, timezone
import logging
import sys
import boto3
from django.conf import settings

logger = logging.getLogger()
BOTO3_METERING_MARKETPLACE_CLIENT = "meteringmarketplace"


def pegBillingCounter(dimension, hosts):
    """
    Send usage quantity to billing API
    """
    mms_client = boto3.client(BOTO3_METERING_MARKETPLACE_CLIENT, region_name=settings.REGION_NAME)
    utc_now = datetime.now(timezone.utc).replace(microsecond=0)
    resource_id = ""
    plan = ""
    managed_app_id = settings.PRODUCT_CODE
    billing_data = {}
    billing_data["resourceId"] = resource_id
    billing_data["dimension"] = dimension
    billing_data["quantity"] = len(hosts)
    billing_data["effectiveStartTime"] = utc_now.isoformat()
    billing_data["planId"] = plan
    logger.debug("Billing payload: %s" % billing_data)
    try:
        response = mms_client.meter_usage(
            ProductCode=settings.PRODUCT_CODE,
            Timestamp=utc_now,
            UsageDimension=dimension,
            UsageQuantity=len(hosts),
        )
        logger.debug("Billing response: %s" % response)
    except Exception as err:
        logger.error("Billing payload not accepted: %s", err)
        logger.error(err)
        sys.exit(1)

    event_id = response.get("MeteringRecordId", "")
    logger.info("Recorded metering event ID: %s" % event_id)

    billing_record = {}
    billing_record["managed_app_id"] = managed_app_id
    billing_record["resource_id"] = resource_id
    billing_record["plan"] = plan
    billing_record["usage_event_id"] = event_id
    billing_record["dimension"] = dimension
    billing_record["hosts"] = ",".join(hosts)
    billing_record["quantity"] = len(hosts)

    return billing_record
