from calendar import monthrange
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from django.db import models

from azure_billing.main.models import JobHostSummary
from azure_billing.billing.models import (
    BilledHost,
    BillingRecord,
    InstallDate,
    RolloverDate,
)

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


def getRolloverDate(current_date=datetime.now(timezone.utc)):
    """
    Sets install date if not already set and calculates the next rollover
    date based on today's date.  Do not set current_date arg except for in tests.
    """
    install_date = getInstallDate()
    # Set to next month with day=1 to ensure no premature rollover
    # and add a month.
    rollover_date = current_date.replace(day=1) + relativedelta(months=1)

    # Make sure next month has enough days, else use last day of month
    days_next_month = monthrange(rollover_date.year, rollover_date.month)[1]
    rollover_date = (
        rollover_date.replace(day=days_next_month)
        if install_date.day > days_next_month
        else rollover_date.replace(day=install_date.day)
    )

    rollover_date, created = RolloverDate.objects.get_or_create(
        pk=1, defaults={"rollover_date": rollover_date}
    )
    rd = rollover_date.rollover_date
    if created:
        logger.debug("Setting rollover date to %s" % rd.strftime("%m-%d-%Y"))
    return rd


def getInstallDate():
    install_date, created = InstallDate.objects.get_or_create(
        pk=1, defaults={"install_date": models.functions.Now()}
    )
    id = InstallDate.objects.get(pk=1).install_date
    if created:
        logger.debug(
            "Setting installation date to %s" % id.strftime("%m-%d-%Y")
        )
    return id


def checkRolloverNeeded(rollover_date):
    """
    True if today is on or after the rollover date
    """
    current_date = datetime.now(timezone.utc)
    return current_date.date() >= rollover_date.date()


def rollover():
    RolloverDate.objects.all().delete()  # Reset rollover date
    # Mark already billed but not rolled over hosts as rolled to reset list
    # (keeping any that would be rolled over but have failed to be billed yet)
    BilledHost.objects.filter(
        rollover_date__isnull=True, billed_date__isnull=False
    ).update(rollover_date=models.functions.Now())


def getUnbilledHosts(startDate):
    """
    Find hosts that were executed against that do not show up
    in the current billing cycle as having been reported.
    """
    executed_hosts = {
        # Stores latest modified execution for hosts with multiple
        # executions
        x.host_name: x.modified
        for x in JobHostSummary.objects.filter(
            modified__gt=startDate
        ).order_by("host_name", "modified")
    }
    billed_hosts = {
        x.host_name: x.billed_date
        for x in BilledHost.objects.filter(rollover_date__isnull=True)
    }
    new_hosts = []
    for host_name in executed_hosts.keys():
        if host_name not in billed_hosts.keys():
            new_hosts.append(host_name)
    return new_hosts


def markHostsBilled(unbilled_hosts):
    """
    Add/update reported hosts in the DB
    """
    for host in unbilled_hosts:
        b = BilledHost(host_name=host, billed_date=models.functions.Now())
        b.save()


def recordBillingInstance(billing_data):
    """
    Store a report of the successful billing
    """
    b = BillingRecord(
        hosts=billing_data["hosts"],
        billed_date=models.functions.Now(),
        dimension=billing_data["dimension"],
        quantity=billing_data["quantity"],
        managed_app_id=billing_data["managed_app_id"],
        resource_id=billing_data["resource_id"],
        plan=billing_data["plan"],
        usage_event_id=billing_data["usage_event_id"],
    )
    b.save()
