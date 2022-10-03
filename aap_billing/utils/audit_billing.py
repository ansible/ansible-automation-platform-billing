#!/usr/bin/env python3

from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.utils import timezone

import argparse
import csv
import django
import os
import sys


def processArgs():
    parser = argparse.ArgumentParser(
        description="AAP Billing Audit Tool",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-v", action="store_true", dest="verbose", help="Include billed hostnames in report")
    return parser.parse_args()


class PeriodRecord:
    def __init__(self, period_date):
        (self.start_date, self.end_date) = db.calcBillingPeriod(period_date)
        self.records = BillingRecord.objects.filter(billed_date__range=(self.start_date, self.end_date)).order_by("-billed_date")
        self.unreported = BilledHost.objects.filter(billed_date__range=(self.start_date, self.end_date), reported=False).order_by("-billed_date")

    def getStartDate(self):
        return self.start_date

    def getEndDate(self):
        return self.end_date

    def getRecords(self):
        return self.records

    def getUnreportedRecords(self):
        return self.unreported


# Main
def main():
    global db, BillingRecord, BilledHost
    args = processArgs()
    # Bootstrap django (orm only)
    os.environ["DJANGO_SETTINGS_MODULE"] = "aap_billing.settings"
    django.setup()
    from aap_billing.db import db  # noqa: E402 - Must follow django setup
    from aap_billing.billing.models import BillingRecord, BilledHost

    # Print header
    csv_out = csv.writer(sys.stdout)
    hosts_or_quant = "Hosts" if args.verbose else "Quantity"
    csv_out.writerow(["Billed Date", "Usage Event ID", hosts_or_quant])
    period_date = db.getDate(db.DateSettingEnum.INSTALL_DATE)
    while period_date < datetime.now(timezone.utc):
        pr = PeriodRecord(period_date)
        records = pr.getRecords()
        unreported = pr.getUnreportedRecords()
        for rec in unreported:
            hosts_or_quant = rec.host_name if args.verbose else 1
            csv_out.writerow([rec.billed_date.strftime("%m/%d/%Y %H:%M:%S"), "included", hosts_or_quant])
        for rec in records:
            hosts_or_quant = rec.hosts if args.verbose else rec.quantity
            csv_out.writerow([rec.billed_date.strftime("%m/%d/%Y %H:%M:%S"), rec.usage_event_id, hosts_or_quant])
        period_date = period_date + relativedelta(months=1)


if __name__ == "__main__":
    main()
