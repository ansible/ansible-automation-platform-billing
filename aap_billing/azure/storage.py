import json
import requests


def fetchBaseQuantity(url, token, offer_id, plan_id):
    """
    Get file from Azure storage at given URL and parse to get base quantity for offer/plan
    """
    url = url + "?" + token
    res = requests.get(url)
    if res.status_code == 200:
        offers_plans = json.loads(res.content)
        for offer in offers_plans["offers"]:
            if offer["id"] == offer_id:
                for plan in offer["plans"]:
                    if plan["id"] == plan_id:
                        return plan["base_quantity"]
    else:
        res.raise_for_status()
    return None
