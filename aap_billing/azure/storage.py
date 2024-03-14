import json
import logging
import requests
import sys


# No longer used - base quantity now loaded from /etc/billingplans/plans.json
def fetchBaseQuantity(url, token, offer_id, plan_id):
    """
    Get file from Azure storage at given URL and parse to get base quantity for offer/plan
    """
    url = url + "?" + token
    # Temporarily disable URL logging to hide token
    logging.disable(logging.DEBUG)
    res = requests.get(url)

    # Reenable logging
    logging.disable(logging.NOTSET)
    if res.status_code == 200:
        offers_plans = json.loads(res.content)
        for offer in offers_plans["offers"]:
            if offer["id"] == offer_id:
                for plan in offer["plans"]:
                    if plan["id"] == plan_id:
                        return plan["base_quantity"]
    else:
        print(f"Failed to fetch billing config file!  Status code: {res.status_code}")
        sys.exit(1)
    return None
