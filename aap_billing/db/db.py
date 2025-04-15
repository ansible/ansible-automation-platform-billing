import json
import logging
from datetime import datetime, timezone
from enum import Enum

import yaml
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from aap_billing import BILLING_INTERFACE_AWS
from aap_billing.billing.models import BaseQuantity, BilledHost, BillingRecord, DateSetting
from aap_billing.main.models import Host, JobHostSummary

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
    LAST_RUN_DATE = 4
    NEW_CALC_DATE = 5  # AAP-21379 Start with counting of ansible_host after this date


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
                install = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                setDate(DateSettingEnum.INSTALL_DATE, install)
                logger.info("New installation, install date [%s]" % install.strftime("%m-%d-%Y"))
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
        DateSetting.objects.update_or_create(name=date_setting.name, defaults={"date": value})
    else:
        logger.error("Invalid date setting: %s" % date_setting)


def calcBillingPeriod(current_date=datetime.now(timezone.utc)):
    """
    Calculates the billing period using install date
    and today's date.
    """
    if settings.BILLING_INTERFACE == BILLING_INTERFACE_AWS:
        period_start = current_date.replace(day=1)
        period_end = period_start + relativedelta(days=-1, months=1)
        return (period_start, period_end)

    install_date = getDate(DateSettingEnum.INSTALL_DATE)
    check_date = install_date
    offset = 0
    while current_date >= check_date:
        offset += 1
        check_date = install_date + relativedelta(months=offset)
    period_start = install_date + relativedelta(months=(offset - 1))
    period_end = install_date + relativedelta(days=-1, months=offset)
    period_end = period_end.replace(hour=23, minute=59, second=59)
    return (period_start, period_end)


def rolloverIfNeeded():
    """
    Determine if the end of the billing period has passed.  If it has,
    mark all accumulated hosts during the preceeding billing period as
    rolled over to start accumulating new hosts for the new billing period.
    """
    (period_start, period_end) = calcBillingPeriod()
    logger.info("Billing period (%s) to (%s)." % (period_start, period_end))
    # Check if stored billing period matches calculated billing period
    if period_start != getDate(DateSettingEnum.PERIOD_START):
        # Use new calculation method on rollover (at install or at next billing period)
        setDate(DateSettingEnum.NEW_CALC_DATE, datetime.now(timezone.utc))

        logger.info("Resetting billed host list.")
        # Set billed hosts as rolled over to reset billing
        BilledHost.objects.filter(rollover_date__isnull=True).update(rollover_date=datetime.now(timezone.utc))
        # Store new billing period
        setDate(DateSettingEnum.PERIOD_START, period_start)
        setDate(DateSettingEnum.PERIOD_END, period_end)


def getProcessedHostCount(startDate):
    """
    Return the number of hosts that have been processed/seen during the current billing period,
    including both free/included and billed hosts.
    """
    processed_hosts = [x.host_name for x in BilledHost.objects.filter(rollover_date__isnull=True)]
    return len(processed_hosts)


def getUnbilledHosts(startDate):
    """
    Find hosts that were executed against that do not show up
    in the current billing cycle as having been reported.
    3-1-2024 - For each host, if it has an "ansible_host" variable defined,
               replace the hostname with the value of that variable.  This
               is intended to bill only once for hosts with multiple aliases
               pointing to the same physical host via "ansible_host". AAP-21379
    """
    executed_hosts = {
        # Grabs latest modified execution for hosts with multiple
        # executions
        x.host_name: x.modified
        for x in JobHostSummary.objects.filter(modified__gt=startDate).order_by("host_name", "modified")
    }
    if getDate(DateSettingEnum.NEW_CALC_DATE) is not None:
        host_list = deduplicateHosts(executed_hosts)
    else:
        host_list = executed_hosts
    billed_hosts = {x.host_name: x.billed_date for x in BilledHost.objects.filter(rollover_date__isnull=True)}
    # Use set to avoid duplicates due to lowercasing
    new_hosts = set()
    for host_name in host_list.keys():
        if host_name.lower() not in billed_hosts.keys():
            new_hosts.add(host_name.lower())
    return list(new_hosts)


def deduplicateHosts(host_list):
    defined_hosts_vars = {x.name: x.variables for x in Host.objects.all()}
    # return [x for x in host_list if x.name in defined_hosts.keys() and "ansible_host" not in ]
    # IF host ID shows up in defined hosts
    # If defined host has variables
    # If variables have ansible_host
    # Then replace host name by value of ansible_host
    deduped_hosts = {}
    for executed_host in host_list.keys():
        variables = {}

        # If this host doesn't have a record (not sure this would ever happen), skip it
        if executed_host not in defined_hosts_vars:
            deduped_hosts[executed_host] = host_list[executed_host]
            continue

        # Variables can be stored as yaml or json
        # Yaml parser SHOULD handle json, but try json parser too just in case
        try:
            variables = yaml.safe_load(defined_hosts_vars[executed_host])
        except yaml.YAMLError:
            logger.error("Unable to parse vars for %s as yaml, trying json", executed_host)
            try:
                variables = json.loads(defined_hosts_vars[executed_host])
            except json.JSONDecodeError:
                logger.error("Unable to parse vars for %s as json, giving up", executed_host)

        # Default to executed_host unless ansible_host is a valid string
        final_host_key = executed_host
        if variables is not None:
            ansible_host_value = variables.get("ansible_host")
            if isinstance(ansible_host_value, str):
                final_host_key = ansible_host_value

        deduped_hosts[final_host_key] = host_list[executed_host]

    return deduped_hosts


def markHostsBilled(unbilled_hosts):
    """
    Add reported hosts in the DB, in billed state
    """
    for host in unbilled_hosts:
        b = BilledHost(host_name=host, billed_date=datetime.now(timezone.utc), reported=True)
        b.save()


def markHostsSeen(unbilled_hosts):
    """
    Add reported hosts to db, but in not billed state
    """
    for host in unbilled_hosts:
        b = BilledHost(host_name=host, billed_date=datetime.now(timezone.utc), reported=False)
        b.save()


def recordBillingInstance(billing_data):
    """
    Store a report of the successful billing
    See azure_ items below for all data returned by Azure
    Marketplace Metered Billing API (plus usage_event_id)
    """
    if settings.BILLING_INTERFACE == BILLING_INTERFACE_AWS:
        b = BillingRecord(
            hosts=billing_data["hosts"],
            billed_date=datetime.now(timezone.utc),
            dimension=billing_data["dimension"],
            quantity=billing_data["quantity"],
            managed_app_id=billing_data["managed_app_id"],
            resource_id=billing_data["resource_id"],
            plan=billing_data["plan"],
            usage_event_id=billing_data["usage_event_id"],
        )
    else:
        # Azure version, add values
        b = BillingRecord(
            hosts=billing_data["hosts"],
            billed_date=datetime.now(timezone.utc),
            dimension=billing_data["dimension"],
            quantity=billing_data["quantity"],
            managed_app_id=billing_data["managed_app_id"],
            resource_id=billing_data["managed_app_id"],
            plan=billing_data["plan"],
            usage_event_id=billing_data["usage_event_id"],
            azure_status=billing_data["azure_status"],
            azure_message_time=billing_data["azure_message_time"],
            azure_resource_id=billing_data["azure_resource_id"],
            azure_quantity=billing_data["azure_quantity"],
            azure_dimension=billing_data["azure_dimention"],
            azure_effective_start_time=billing_data["azure_effective_start_time"],
            azure_plan_id=billing_data["azure_plan_id"],
        )

    b.save()


def recordLastRunDateTime():
    """
    Store current date/time as marker for last time this module ran.
    (main purpose is to ensure database availability/writeability)
    """
    setDate(DateSettingEnum.LAST_RUN_DATE, datetime.now(timezone.utc))


def getBaseQuantity():
    """
    Retrieve base quantity from db
    """
    try:
        res = BaseQuantity.objects.filter(plan_id="unused", offer_id="unused").get()
        base_quantity = res.base_quantity
    except ObjectDoesNotExist:
        return None
    return base_quantity


def recordBaseQuantity(base_quantity):
    """
    Store the base quantity
    """
    res, created = BaseQuantity.objects.update_or_create(plan_id="unused", offer_id="unused", defaults={"base_quantity": base_quantity})
    if not created:
        msg = "Attempting to set base quantity when already set"
        logger.error(msg)
        raise RuntimeError(msg)
    logging.info("Base quantity set to [%d]" % (res.base_quantity))


def getHostsToBill(period_start, base_quantity):
    """
    Find new automated hosts, determine if they are included or should be billed
    and return both lists (to_bill, to_mark_included).
    """
    processed_host_count = getProcessedHostCount(period_start)
    logger.debug("Current processed host count is [%d]" % processed_host_count)
    unbilled = getUnbilledHosts(period_start)
    logger.debug("New unprocessed host count is [%d]" % len(unbilled))

    hosts_to_bill = []
    hosts_to_mark = []
    if (processed_host_count + len(unbilled)) > base_quantity:
        # Some or all exceed base quantity, mark and bill appropriate sets
        number_to_report = processed_host_count + len(unbilled) - base_quantity
        hosts_to_bill = unbilled[0:number_to_report]
        hosts_to_mark = unbilled[number_to_report:]
    else:
        # None exceed base quantity, mark all but don't bill
        hosts_to_mark = unbilled
    return (hosts_to_bill, hosts_to_mark)
