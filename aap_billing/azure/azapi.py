import logging
import os
import sys
from datetime import datetime, timezone

import requests

metadata_ip = "169.254.169.254"
metadata_header = {"Metadata": "true"}
token_api_version = "2018-02-01"
instance_api_version = "2019-06-01"
subscription_api_version = "2019-10-01"
managed_app_api_version = "2019-07-01"
usage_api_version = "2018-08-31"
billing_api_version = "2018-08-31"

logger = logging.getLogger()

metadata_loaded = False
metadata = {}


def _getJsonPayload(url, headers, data_type="data"):
    """
    Perform get and parse response
    """
    try:
        response = requests.get(url, headers=headers)
    except requests.exceptions.RequestException as e:
        logger.error("Unable to get %s from Azure, abort: %s" % (data_type, repr(e)))
        sys.exit(1)
    response.raise_for_status()
    return response.json()


def _fetchMSIAccessToken():
    """
    Fetch the system identity access token from the metadata store
    """
    resource = "https%3A%2F%2Fmanagement.azure.com%2F"
    url = "http://%s/metadata/identity/oauth2/token?api-version=%s&resource=%s" % (metadata_ip, token_api_version, resource)
    j = _getJsonPayload(url, metadata_header, "access token")
    token = j["access_token"]
    logger.debug("Fetched access token.")
    return token


def _fetchWorkloadIdentityAccessToken():
    """
    Fetch the access token using the new workload identity method
    """
    req = {}
    try:
        tenant = os.environ["AZURE_TENANT_ID"]
        req["client_id"] = os.environ["AZURE_CLIENT_ID"]
        auth_host = os.environ["AZURE_AUTHORITY_HOST"]
        token_file = os.environ["AZURE_FEDERATED_TOKEN_FILE"]

        with open(token_file, "r") as tf:
            req["client_assertion"] = tf.read().strip()
    except (KeyError, FileNotFoundError):
        logger.error("Workload identity not configured on this pod")
        return None

    req["grant_type"] = "client_credentials"
    req["client_assertion_type"] = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
    req["scope"] = "https://management.azure.com//.default"  # The double // is very important

    auth_url = f"{auth_host}{tenant}/oauth2/v2.0/token"

    resp = requests.post(auth_url, data=req)
    resp.raise_for_status()
    if "access_token" not in resp.json():
        logger.error("Access token not returned.")
        return None
    else:
        return resp.json()["access_token"]


def _fetchSubscriptionAndNodeResourceGroup():
    """
    Fetch subscription and node resource group from the metadata store
    """
    url = "http://%s/metadata/instance?api-version=%s" % (
        metadata_ip,
        instance_api_version,
    )
    j = _getJsonPayload(url, metadata_header, "subscription")
    subId = j["compute"]["subscriptionId"]
    nrg = j["compute"]["resourceGroupName"]
    logger.debug("Fetched subscription ID (%s) and node resource group (%s)." % (subId, nrg))
    return (subId, nrg)


def _fetchManagedAppId(subscription_id, resource_group_name, access_token):
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


def _fetchManagedResourceGroup(subscription_id, node_resource_group_name, access_token):
    """
    Fetch managed resource group name from node resource group metadata
    """
    auth_header = {"Authorization": "Bearer %s" % access_token}
    base = "https://management.azure.com/subscriptions"
    url = "%s/%s/resourceGroups/%s?api-version=%s" % (
        base,
        subscription_id,
        node_resource_group_name,
        subscription_api_version,
    )
    j = _getJsonPayload(url, auth_header, "managed resource group")
    managed_resource_group = j["tags"]["aks-managed-cluster-rg"]
    logger.debug("Fetched managed resource group (%s)" % managed_resource_group)
    return managed_resource_group


def _stripPreviewSuffix(text):
    # Preview offers have -preview appended
    suffix = "-preview"
    if text.endswith(suffix):
        return text[: -len(suffix)]
    return text


def getManAppIdAndMetadata():
    """
    Grab various info from metadata
    """
    global metadata_loaded
    global metadata  # noqa: F824

    if metadata_loaded:
        return metadata
    else:
        token = _fetchWorkloadIdentityAccessToken()
        if not token:
            logger.info("Workload identity token request failed, trying pod identity.")
            token = _fetchMSIAccessToken()
        (sub, nrg) = _fetchSubscriptionAndNodeResourceGroup()
        mrg = _fetchManagedResourceGroup(sub, nrg, token)
        managed_app_id = _fetchManagedAppId(sub, mrg, token)
        metadata["token"] = token
        metadata["managed_app_id"] = managed_app_id
        metadata_loaded = True
    return metadata


def pegBillingCounter(plan_id, dimension, hosts):
    """
    Send usage quantity to billing API
    """
    metadata = getManAppIdAndMetadata()
    billing_data = {}
    billing_data["resourceUri"] = metadata["managed_app_id"]
    billing_data["dimension"] = dimension
    billing_data["quantity"] = len(hosts)
    billing_data["effectiveStartTime"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    billing_data["planId"] = plan_id
    logger.debug("Billing payload: %s" % billing_data)
    auth_header = {"Authorization": "Bearer %s" % metadata["token"]}
    url = "https://marketplaceapi.microsoft.com/api/usageEvent?api-version=%s" % billing_api_version
    try:
        response = requests.post(url, headers=auth_header, json=billing_data)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error("Billing payload not accepted: %s", e)
        logger.error(response.text)
        sys.exit(1)

    logger.debug("Billing response: %s" % response.json())
    responseJson = response.json()
    event_id = responseJson["usageEventId"]
    logger.info("Recorded metering event ID: %s" % event_id)

    billing_record = {}
    billing_record["managed_app_id"] = metadata["managed_app_id"]
    billing_record["resource_uri"] = metadata["managed_app_id"]
    billing_record["plan"] = plan_id
    billing_record["usage_event_id"] = event_id
    billing_record["dimension"] = dimension
    billing_record["hosts"] = ",".join(hosts)
    billing_record["quantity"] = len(hosts)

    billing_record["azure_status"] = responseJson["status"]
    billing_record["azure_message_time"] = responseJson["messageTime"]
    billing_record["azure_resource_id"] = responseJson["resourceId"] if "resourceId" in responseJson else None
    billing_record["azure_resource_uri"] = responseJson["resourceUri"] if "resourceUri" in responseJson else None
    billing_record["azure_quantity"] = responseJson["quantity"]
    billing_record["azure_dimention"] = responseJson["dimension"]
    billing_record["azure_effective_start_time"] = responseJson["effectiveStartTime"]
    billing_record["azure_plan_id"] = responseJson["planId"]

    return billing_record
