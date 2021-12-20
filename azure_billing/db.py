from django.db import models

from main.models import JobHostSummary
from billing.models import BilledHost
from billing.models import BillingRecord

import logging

logger = logging.getLogger()


class BillingRouter:
    """
    Routes db queries to proper database
    """

    def db_for_read(self, model, **hints):
        if model._meta.app_label == "main":
            return "awx"
        else:
            return "default"

    def db_for_write(self, model, **hints):
        if model._meta.app_label == "billing":
            return "default"
        return None

    def allow_relation(self, obj1, obj2, **hints):
        # If multiple tables added to billing db, update this to allow
        # relationships between tables in that db.
        return False

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Allow migrations only for the default database
        if db == "default":
            return app_label == "billing"
        return None


def getUnbilledHosts():
    """
    Find hosts that were executed against that do not show up
    in the current billing cycle as having been reported.
    """
    # TODO Add billing period logic
    executed_hosts = {
        x.host_name: x.modified
        for x in JobHostSummary.objects.order_by(
            "host_name", "-modified"
        ).distinct("host_name")
    }
    billed_hosts = {
        x.host_name: x.billed_date for x in BilledHost.objects.all()
    }
    new_hosts = []
    for host_name in executed_hosts.keys():
        if host_name not in billed_hosts.keys():
            new_hosts.append(host_name)
        elif executed_hosts[host_name] > billed_hosts[host_name]:
            # Seen it, but executed again since last report
            # Keep track of this or don't care?
            pass
        else:
            # Do nothing, already reported
            pass
    return new_hosts


def markHostsBilled(unbilled_hosts):
    """
    Add/update reported hosts in the DB
    """
    for host in unbilled_hosts:
        b = BilledHost(host_name=host, billed_date=models.functions.Now())
        # TODO b.save()


def recordBillingInstance(billing_data):
    """
    Store a report of the successful billing
    """
    b = BillingRecord(
        hosts=",".join(billing_data["hosts"]),
        billed_date=models.functions.Now(),
        dimension=billing_data["dimension"],
        quantity=len(billing_data["hosts"]),
        managed_app_id=billing_data["managed_app_id"],
        resource_id=billing_data["resource_id"],
        plan=billing_data["plan"],
        usage_event_id=billing_data["usage_event_id"],
    )
    b.save()
