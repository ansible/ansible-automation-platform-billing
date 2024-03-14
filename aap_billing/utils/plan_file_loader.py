import json


def fetchBaseQuantity(offer_id, plan_id):
    """
    Read plans.json and parse to get base quantity for offer/plan
    """
    try:
        plan_file = open("/etc/billingplans/plans.json")
    except Exception as e:
        print(f"Unable to open /etc/billingplans/plans.json: {e}")
        return None
    with plan_file:
        try:
            offers_plans = json.load(plan_file)
        except json.JSONDecodeError as e:
            print(f"Failed to read json from /etc/billingplans/plans.json: {e}")
            print("Base quantity unknown.")
            return None
        for offer in offers_plans["offers"]:
            if offer["id"] == offer_id:
                for plan in offer["plans"]:
                    if plan["id"] == plan_id:
                        return plan["base_quantity"]
