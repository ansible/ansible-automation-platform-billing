from aap_billing.azure import azapi
from aap_billing.billing.models import BilledHost, BillingRecord
from aap_billing.main.models import JobHostSummary
from aap_billing.db import db
from datetime import datetime
from django.conf import settings
from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone
from unittest import mock


def mocked_azure_apis(*args, **kwargs):
    """
    Handles intercepted gets and posts sending a
    mocked response based on the URL content.
    """

    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            return self.json_data

        def raise_for_status(*args):
            pass

    if "token" in args[0]:
        # Return access token packet
        data = {"access_token": "tokentokentoken"}
        return MockResponse(data, 200)
    elif "instance" in args[0]:
        # Return instance packet
        data = {
            "compute": {
                "subscriptionId": "subscription123",
                "resourceGroupName": "node_resource_group",
            }
        }
        return MockResponse(data, 200)
    elif "resourceGroups" in args[0]:
        # Return merged resource group packet
        data = {
            "managedBy": "applications",
            "tags": {"aks-managed-cluster-rg": "resource_group"},
        }
        return MockResponse(data, 200)
    elif "applications" in args[0]:
        # Return managed application packet
        data = {
            "properties": {
                "billingDetails": {"resourceUsageId": "resource_usage_id_val"}
            },
            "plan": {"name": "scottsplan"},
        }
        return MockResponse(data, 200)
    elif "usageEvent" in args[0]:
        # Return billing response
        data = {
            "usageEventId": "usage_event_id_val",
            "status": "Accepted",
            "messageTime": datetime.now(timezone.utc).isoformat(),
            "resourceId": "resource_usage_id_val",
            "quantity": 5,
            "dimension": settings.DIMENSION,
            "effectiveStartTime": datetime.now(timezone.utc).isoformat(),
            "planId": "plan0",
        }
        return MockResponse(data, 200)
    return MockResponse(None, 404)


class BillingTests(TransactionTestCase):
    """
    Replicates actions of main method in test environment
    """

    fixtures = ["hosts", "billed"]

    @classmethod
    def setUpClass(cls):
        super(BillingTests, cls).setUpClass()

        # Create unmanaged job host summary table
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(JobHostSummary)

    @mock.patch("requests.get", side_effect=mocked_azure_apis)
    @mock.patch("requests.post", side_effect=mocked_azure_apis)
    def testMain(self, mock_get, mock_post):
        db.setDate(
            db.DateSettingEnum.INSTALL_DATE,
            datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        )
        today = datetime(2022, 2, 7, tzinfo=timezone.utc)
        (period_start, _) = db.calcBillingPeriod()
        unbilled = db.getUnbilledHosts(period_start)  # 2 hosts from fixtures
        self.assertEqual(len(unbilled), 2)
        billing_record = azapi.pegBillingCounter(settings.DIMENSION, unbilled)
        db.recordBillingInstance(billing_record)
        records = BillingRecord.objects.all()  # One new record
        self.assertEqual(len(records), 1)
        db.markHostsBilled(unbilled)  # Mark as billed
        BilledHost.objects.all()  # Verify billed_date is today
        for billed_host in BilledHost.objects.all():
            if billed_host in unbilled:
                self.assertEqual(billed_host.billed_date.date(), today.date())

        # Update billing period directly
        db.setDate(
            db.DateSettingEnum.PERIOD_START,
            datetime(2022, 2, 7, 0, 0, 0, tzinfo=timezone.utc),
        )
        db.setDate(
            db.DateSettingEnum.PERIOD_END,
            datetime(2022, 3, 6, 0, 0, 0, tzinfo=timezone.utc),
        )
        # Do rollover
        db.rolloverIfNeeded()
        unbilled = db.getUnbilledHosts(
            period_start
        )  # Billed hosts cleared, all 3 are unbilled
        self.assertEqual(len(unbilled), 3)

    def testHostsToReport(self):
        hosts = db.getUnbilledHosts(
            datetime(2021, 12, 31, tzinfo=timezone.utc)
        )
        expectedUnbilled = ["host2", "host3"]
        self.assertEqual(len(hosts), 2)
        for host in hosts:
            self.assertIn(host, expectedUnbilled)

    def testMarkHostsBilled(self):
        hosts = db.getUnbilledHosts(
            datetime(2021, 12, 31, tzinfo=timezone.utc)
        )
        db.markHostsBilled(hosts)
        for host in hosts:
            qs = BilledHost.objects.filter(host_name=host).order_by(
                "-billed_date"
            )
            self.assertTrue(qs.exists())
            self.assertEqual(qs.first().rollover_date, None)
        shouldbezero = db.getUnbilledHosts(
            datetime(2021, 12, 31, tzinfo=timezone.utc)
        )
        self.assertEqual(len(shouldbezero), 0)

    def testSeedInstallDate(self):
        installDate = db.getDate(db.DateSettingEnum.INSTALL_DATE)
        self.assertEqual(installDate.date(), datetime.now(timezone.utc).date())

    def testBillingPeriodCalc(self):
        # "today" is 1-15-2022
        # Install dates: Dec 1, 15, 31 2021
        # (inst date, exp start date, exp end date)
        today = datetime(2022, 1, 15, tzinfo=timezone.utc)
        data = [
            (2021, 12, 1, 2022, 1, 1, 2022, 1, 31),
            (2021, 12, 15, 2022, 1, 15, 2022, 2, 14),
            (2021, 12, 31, 2021, 12, 31, 2022, 1, 30),
        ]
        for datum in data:
            db.setDate(
                db.DateSettingEnum.INSTALL_DATE,
                datetime(datum[0], datum[1], datum[2], tzinfo=timezone.utc),
            )
            (period_start, period_end) = db.calcBillingPeriod(today)
            self.assertEqual(period_start.year, datum[3])
            self.assertEqual(period_start.month, datum[4])
            self.assertEqual(period_start.day, datum[5])
            self.assertEqual(period_end.year, datum[6])
            self.assertEqual(period_end.month, datum[7])
            self.assertEqual(period_end.day, datum[8])

    def testBillingPeriodSpecial(self):
        # Test february since it is short
        # Install dates: Dec 1, 15, 31 2021
        # (inst date, exp start date, exp end date)
        today = datetime(2022, 2, 15, tzinfo=timezone.utc)
        data = [
            (2021, 12, 1, 2022, 2, 1, 2022, 2, 28),
            (2021, 12, 31, 2022, 1, 31, 2022, 2, 27),
        ]
        for datum in data:
            db.setDate(
                db.DateSettingEnum.INSTALL_DATE,
                datetime(datum[0], datum[1], datum[2], tzinfo=timezone.utc),
            )
            (period_start, period_end) = db.calcBillingPeriod(today)
            self.assertEqual(period_start.year, datum[3])
            self.assertEqual(period_start.month, datum[4])
            self.assertEqual(period_start.day, datum[5])
            self.assertEqual(period_end.year, datum[6])
            self.assertEqual(period_end.month, datum[7])
            self.assertEqual(period_end.day, datum[8])

    @mock.patch("requests.get", side_effect=mocked_azure_apis)
    @mock.patch("requests.post", side_effect=mocked_azure_apis)
    def testBillingApi(self, mock_get, mock_post):
        today = datetime.now(timezone.utc)

        hosts = db.getUnbilledHosts(
            datetime(2021, 12, 31, tzinfo=timezone.utc)
        )
        billing_data = azapi.pegBillingCounter(settings.DIMENSION, hosts)
        db.recordBillingInstance(billing_data)
        record = BillingRecord.objects.first()
        self.assertEqual(record.quantity, 2)
        self.assertEqual(record.billed_date.day, today.day)
        self.assertEqual(record.billed_date.month, today.month)
        self.assertEqual(record.billed_date.year, today.year)
