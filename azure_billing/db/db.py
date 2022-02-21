from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from enum import Enum

from azure_billing.main.models import JobHostSummary
from azure_billing.billing.models import BilledHost, BillingRecord, DateSetting

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
        # Update if needed
        return False

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Allow migrations only for the default database
        if db == "default":
            return app_label == "billing"
        return None


class DateSettingEnum(Enum):
    INSTALL_DATE = 1
    PERIOD_START = 2
    PERIOD_END = 3


def getDate(date_setting):
    """
    Gets current date val from db
    """
    if isinstance(date_setting, DateSettingEnum):
        try:
            qs = DateSetting.objects.filter(name=date_setting.name).get()
        except ObjectDoesNotExist:
            # Special handling for install date, set it if empty
            if date_setting == DateSettingEnum.INSTALL_DATE:
                install = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                setDate(DateSettingEnum.INSTALL_DATE, install)
                logger.info(
                    "New installation, install date [%s]"
                    % install.strftime("%m-%d-%Y")
                )
                return install
            return None
        return qs.date
    else:
        logger.error("Invalid date setting: %s" % date_setting)


def setDate(date_setting, value):
    """
    Sets date val in db
    """
    if isinstance(date_setting, DateSettingEnum):
        DateSetting.objects.update_or_create(
            name=date_setting.name, defaults={"date": value}
        )
    else:
        logger.error("Invalid date setting: %s" % date_setting)


def calcBillingPeriod(current_date=datetime.now(timezone.utc)):
    """
    Calculates the billing period using install date
    and today's date.
    """
    install_date = getDate(DateSettingEnum.INSTALL_DATE)
    check_date = install_date
    offset = 0
    while current_date >= check_date:
        offset += 1
        check_date = install_date + relativedelta(months=offset)
    period_start = install_date + relativedelta(months=(offset - 1))
    period_end = install_date + relativedelta(days=-1, months=offset)
    return (period_start, period_end)


def rolloverIfNeeded():
    (period_start, period_end) = calcBillingPeriod()
    logger.info("Billing period (%s) to (%s)." % (period_start, period_end))
    # Check if stored billing period matches calculated billing period
    if period_start != getDate(DateSettingEnum.PERIOD_START):
        logger.info("Resetting billed host list.")
        # Set billed hosts as rolled over to reset billing
        BilledHost.objects.filter(rollover_date__isnull=True).update(
            rollover_date=models.functions.Now()
        )
        # Store new billing period
        setDate(DateSettingEnum.PERIOD_START, period_start)
        setDate(DateSettingEnum.PERIOD_END, period_end)


def getUnbilledHosts(startDate):
    """
    Find hosts that were executed against that do not show up
    in the current billing cycle as having been reported.
    """
    executed_hosts = {
        # Grabs latest modified execution for hosts with multiple
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
    Add reported hosts in the DB
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
