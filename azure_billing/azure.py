from datetime import datetime
import logging
import requests
import sys

metadata_ip = "169.254.169.254"
metadata_header = {"Metadata": "true"}
token_api_version = "2018-02-01"
instance_api_version = "2019-06-01"
subscription_api_version = "2019-10-01"
managed_app_api_version = "2019-07-01"
usage_api_version = "2018-08-31"
billing_api_version = "2018-08-31"

logger = logging.getLogger()


def _getJsonPayload(url, headers, data_type="data"):
    """
    Perform get and parse response
    """
    try:
        response = requests.get(url, headers=headers)
    except requests.exceptions.RequestException as e:
        logger.error(
            "Unable to get %s from Azure, abort: %s" % (data_type, repr(e))
        )
        sys.exit(1)
    response.raise_for_status()
    return response.json()


def fetchAccessToken():
    """
    Fetch the system identity access token from the metadata store
    """
    resource = "https%3A%2F%2Fmanagement.azure.com%2F"
    url = (
        "http://%s/metadata/identity/oauth2/token?api-version=%s&resource=%s"
        % (metadata_ip, token_api_version, resource)
    )
    j = _getJsonPayload(url, metadata_header, "access token")
    token = j["access_token"]
    logger.debug("Fetched access token.")
    return token


def fetchSubscriptionAndRG():
    """
    Fetch the current subscription and resource group from the metadata store
    """
    url = "http://%s/metadata/instance?api-version=%s" % (
        metadata_ip,
        instance_api_version,
    )
    j = _getJsonPayload(
        url, metadata_header, "subscription and resource group"
    )
    subId = j["compute"]["subscriptionId"]
    rg = j["compute"]["resourceGroupName"]
    logger.debug(
        "Fetched subscription ID (%s) and resource group (%s)." % (subId, rg)
    )
    return (subId, rg)


def fetchManagedAppId(subscription_id, resource_group_name, access_token):
    """
    Fetch current managed application ID
    """
    auth_header = {"Authorization": "Bearer %s" % access_token}
    base = "https://management.azure.com/subscriptions"
    url = "%s/%s/resourceGroups/%s?api-version=%s" % (
        base,
        subscription_id,
        resource_group_name,
        subscription_api_version,
    )
    j = _getJsonPayload(url, auth_header, "managed app ID")
    managed_app_id = j["managedBy"]
    logger.debug("Fetched managed app ID (%s)" % managed_app_id)
    return managed_app_id


def fetchResourceIdAndPlan(managed_app_id, access_token):
    """
    Fetch resource usage ID and plan for app
    """
    auth_header = {"Authorization": "Bearer %s" % access_token}
    url = "https://management.azure.com%s?api-version=%s" % (
        managed_app_id,
        managed_app_api_version,
    )
    j = _getJsonPayload(url, auth_header, "resource usage ID and plan")
    resource_id = j["properties"]["billingDetails"]["resourceUsageId"]
    plan = j["plan"]["name"]
    logger.debug(
        "Fetched resource ID (%s) and plan (%s)" % (resource_id, plan)
    )
    return (resource_id, plan)


def pegBillingCounter(dimension, quantity):
    """
    Send usage quantity to billing API
    """
    token = fetchAccessToken()
    (sub, rg) = fetchSubscriptionAndRG()
    managed_app_id = fetchManagedAppId(sub, rg, token)
    (resource_id, plan) = fetchResourceIdAndPlan(managed_app_id, token)

    billing_data = {}
    billing_data["resourceId"] = resource_id
    billing_data["dimension"] = dimension
    billing_data["quantity"] = quantity
    billing_data["effectiveStartTime"] = (
        datetime.now().replace(microsecond=0).isoformat()
    )
    billing_data["planId"] = plan
    logger.debug("Billing payload: %s" % billing_data)
    auth_header = {"Authorization": "Bearer %s" % token}
    url = (
        "https://marketplaceapi.microsoft.com/api/usageEvent?api-version=%s"
        % billing_api_version
    )
    try:
        response = requests.post(url, headers=auth_header, data=billing_data)
    except requests.exceptions.RequestException as e:
        logger.error("Unable to send data to Azure, abort: %s" % repr(e))

    # TODO response.raise_for_status()
    logger.debug("Billing response: %s" % response.text)

    # TODO Populate this when billing is working (from response)
    usage_event_id = "TBD"

    billing_record = {}
    billing_record["managed_app_id"] = managed_app_id
    billing_record["resource_id"] = resource_id
    billing_record["plan"] = plan
    billing_record["usage_event_id"] = usage_event_id

    return billing_record
