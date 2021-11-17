from datetime import datetime
import json
import requests

metadata_ip = "169.254.169.254"
metadata_header = {"Metadata": "true"}
token_api_version = "2018-02-01"
instance_api_version = "2019-06-01"
subscription_api_version = "2019-10-01"
usage_api_version = "2018-08-31"


# Fetch the system identity access token from the metadata store
def fetchAccessToken():
    resource = "https%3A%2F%2Fmanagement.azure.com%2F"
    url = "http://%s/metadata/identity/oauth2/token?api-version=%s&resource=%s" % (metadata_ip, token_api_version, resource)

    response = requests.get(url, headers=metadata_header)
    j = response.json()
    token=j['access_token']
    return token

# Fetch the current subscription and resource group from the metadata store
def fetchSubscriptionAndRG():
    url = "http://%s/metadata/instance?api-version=%s" % (metadata_ip, instance_api_version)
    response = requests.get(url, headers=metadata_header)
    j = response.json()
    subId=j['compute']['subscriptionId']
    rg=j['compute']['resourceGroupName']
    return (subId, rg)

# Fetch current managed application ID
def fetchManagedAppId(subscription_id, resource_group_name, access_token):
    auth_header = {"Authorization": "Bearer %s" % access_token}
    url = "https://management.azure.com/subscriptions/%s/resourceGroups/%s?api-version=%s" % (subscription_id, resource_group_name, subscription_api_version)
    response = requests.get(url, headers=auth_header)
    j = response.json()
    managed_app_id=j['managedBy']
    return managed_app_id

def pegBillingCounter(plan, dimension, quantity):
    # TODO Not working currently, fix up when working in Azure environment.
    token = 'token' #fetchAccessToken()
    (sub, rg) = ('sub', 'rg') #fetchSubscriptionAndRG()
    managed_app_id = '12345' #fetchManagedAppId(sub, rg, token)
    
    billing_data = {}
    billing_data['resourceId'] = managed_app_id
    billing_data['dimension'] = dimension 
    billing_data['quantity'] = quantity 
    billing_data['effectiveStartTime'] = datetime.now().replace(microsecond=0).isoformat()
    billing_data['planId'] = plan

    print("Would send %s to https://marketplaceapi.microsoft.com/api/usageEvent?api-version=%s" % (json.dumps(billing_data, indent=3), usage_api_version))
