from azure_billing.cli import main
from azure_billing.azure import azapi
from azure_billing.billing.models import BilledHost, BillingRecord, InstallDate
from azure_billing.db import db
from azure_billing.main.models import JobHostSummary
from calendar import monthrange
from datetime import datetime
from django.conf import settings
from django.core.management import call_command
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


class MainTest(TransactionTestCase):
    """
    Replicates actions of main method in test environment
    """

    fixtures = ["hosts", "billed", "installdate", "rolloverdate"]

    @classmethod
    def setUpClass(cls):
        super(MainTest, cls).setUpClass()
        call_command("migrate", interactive=False)

    @mock.patch("requests.get", side_effect=mocked_azure_apis)
    @mock.patch("requests.post", side_effect=mocked_azure_apis)
    def testMain(self, mock_get, mock_post):
        today = datetime(2022, 2, 7, tzinfo=timezone.utc)

        rollover_date = db.getRolloverDate()  # fixture val, 2-1-22
        unbilled = db.getUnbilledHosts(rollover_date)  # 2 hosts from fixtures
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

        self.assertTrue(db.checkRolloverNeeded(rollover_date))
        db.rollover()  # Marks all billed hosts as rolled over, clears rolloverdate
        rollover_date = db.getRolloverDate(today)  # Calculated val, 3-1-2022
        self.assertEqual(
            rollover_date.date(),
            datetime(2022, 3, 1, tzinfo=timezone.utc).date(),
        )

        unbilled = db.getUnbilledHosts(
            rollover_date
        )  # Billed hosts cleared, all 3 are unbilled
        self.assertEqual(len(unbilled), 3)


class DbTests(TransactionTestCase):
    """
    Test non-billing period db functions independently
    """

    fixtures = ["hosts", "billed", "rolloverdate"]

    @classmethod
    def setUpClass(cls):
        super(DbTests, cls).setUpClass()
        call_command("migrate", interactive=False)

    def testHostsToReport(self):
        rollover_date = db.getRolloverDate()
        hosts = db.getUnbilledHosts(rollover_date)
        expectedUnbilled = ["host2", "host3"]
        self.assertEqual(len(hosts), 2)
        for host in hosts:
            self.assertIn(host, expectedUnbilled)

    def testMarkHostsBilled(self):
        rollover_date = db.getRolloverDate()
        hosts = db.getUnbilledHosts(rollover_date)
        db.markHostsBilled(hosts)
        for host in hosts:
            qs = BilledHost.objects.filter(host_name=host)
            self.assertTrue(qs.exists())
            self.assertEqual(qs.get().rollover_date, None)
        shouldbezero = db.getUnbilledHosts(rollover_date)
        self.assertEqual(len(shouldbezero), 0)


class BillingPeriodTests(TransactionTestCase):
    """
    Billing period related functions
    """

    fixtures = ["billed"]

    @classmethod
    def setUpClass(cls):
        super(BillingPeriodTests, cls).setUpClass()
        call_command("migrate", interactive=False)

    def testSeedInstallDate(self):
        db.getRolloverDate()
        installDate = db.getInstallDate()
        self.assertEqual(installDate.date(), datetime.now(timezone.utc).date())

    def testRolloverToday(self):
        today = datetime.now(timezone.utc)
        for day_of_month in range(1, 32):
            InstallDate.objects.update_or_create(
                pk=1,
                defaults={
                    "install_date": datetime(
                        2022, 1, day_of_month, tzinfo=timezone.utc
                    )
                },
            )
            db.rollover()  # Reset rolloverdate
            rolloverDate = db.getRolloverDate()
            days_next_month = monthrange(today.year, today.month + 1)[1]
            self.assertEqual(
                rolloverDate.day,
                day_of_month
                if days_next_month >= day_of_month
                else days_next_month,
            )
            self.assertEqual(rolloverDate.month, today.month + 1)
            self.assertEqual(rolloverDate.year, today.year)

    def testRolloverSpecial(self):
        # Test february rollover month since it is short
        air_quote_today = datetime(2022, 1, 15, tzinfo=timezone.utc)
        for day_of_month in range(1, 32):
            InstallDate.objects.update_or_create(
                pk=1,
                defaults={
                    "install_date": datetime(
                        2022, 1, day_of_month, tzinfo=timezone.utc
                    )
                },
            )
            db.rollover()  # Reset rolloverdate
            rolloverDate = db.getRolloverDate(air_quote_today)
            days_next_month = monthrange(
                air_quote_today.year, air_quote_today.month + 1
            )[1]
            self.assertEqual(
                rolloverDate.day,
                day_of_month
                if days_next_month >= day_of_month
                else days_next_month,
            )
            self.assertEqual(rolloverDate.month, air_quote_today.month + 1)
            self.assertEqual(rolloverDate.year, air_quote_today.year)


class BillingApiTests(TransactionTestCase):
    """
    Azure billing API (mocked) related tests
    """

    fixtures = ["hosts", "rolloverdate"]

    @classmethod
    def setUpClass(cls):
        super(BillingApiTests, cls).setUpClass()
        call_command("migrate", interactive=False)

    @mock.patch("requests.get", side_effect=mocked_azure_apis)
    @mock.patch("requests.post", side_effect=mocked_azure_apis)
    def testBillingApi(self, mock_get, mock_post):
        today = datetime.now(timezone.utc)

        rollover_date = db.getRolloverDate()
        hosts = db.getUnbilledHosts(rollover_date)
        billing_data = azapi.pegBillingCounter(settings.DIMENSION, hosts)
        db.recordBillingInstance(billing_data)
        record = BillingRecord.objects.first()
        self.assertEqual(record.quantity, 3)
        self.assertEqual(record.billed_date.day, today.day)
        self.assertEqual(record.billed_date.month, today.month)
        self.assertEqual(record.billed_date.year, today.year)
