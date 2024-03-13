from aap_billing import BILLING_INTERFACE_AWS
from aap_billing import BILLING_INTERFACE_AZURE
from aap_billing import cli
from aap_billing.aws import awsapi
from aap_billing.azure import azapi
from aap_billing.billing.models import BilledHost, BillingRecord
from aap_billing.main.models import JobHostSummary, Host
from aap_billing.db import db
from datetime import datetime, timezone
from django.conf import settings
from django.db import connection
from django.test import TransactionTestCase
from io import StringIO
from unittest import mock
import botocore

orig = botocore.client.BaseClient._make_api_call


def mock_make_api_call(self, operation_name, kwarg):
    if operation_name == "MeterUsage":
        return {"MeteringRecordId": 1}
    return orig(self, operation_name, kwarg)


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
        data = {"compute": {"subscriptionId": "subscription123", "resourceGroupName": "node_resource_group"}}
        return MockResponse(data, 200)
    elif "resourceGroups" in args[0]:
        # Return merged resource group packet
        data = {"managedBy": "applications", "tags": {"aks-managed-cluster-rg": "resource_group"}}
        return MockResponse(data, 200)
    elif "applications" in args[0]:
        # Return managed application packet
        data = {
            "properties": {"billingDetails": {"resourceUsageId": "resource_usage_id_val"}},
            "plan": {"name": "scottsplan", "product": "bhavensttest-preview"},
            "kind": "MarketPlace",
        }
        return MockResponse(data, 200)
    elif "usageEvent" in args[0]:
        # Return billing response
        data = {
            "usageEventId": "12345678-90ab-cdef-0123-4567890abcde",
            "status": "Accepted",
            "messageTime": "2020-01-12T13:19:35.3458658Z",
            "resourceId": "12345678-90ab-cdef-0123-4567890abcde",
            "quantity": 5.0,
            "dimension": settings.DIMENSION,
            "effectiveStartTime": "2018-12-01T08:30:14",
            "planId": "plan0",
        }
        return MockResponse(data, 200)
    return MockResponse(None, 404)


def mocked_storage_file(*args, **kwargs):
    data = '{"offers": [{"name": "Bryan Test", "id": "bhavensttest", "plans": [{"name": "Updated Dimension", "id": "plan7", "base_quantity": 0}]}]}'
    return StringIO(data)


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
            schema_editor.create_model(Host)

    @mock.patch("requests.get", side_effect=mocked_azure_apis)
    @mock.patch("requests.post", side_effect=mocked_azure_apis)
    def testMainAzure(self, mock_get, mock_post):
        with self.settings(BILLING_INTERFACE=BILLING_INTERFACE_AZURE):
            db.setDate(
                db.DateSettingEnum.INSTALL_DATE,
                datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            )
            today = datetime(2022, 2, 7, tzinfo=timezone.utc)
            db.recordLastRunDateTime()
            run_date = db.getDate(db.DateSettingEnum.LAST_RUN_DATE)
            self.assertEqual(run_date.day, datetime.now(timezone.utc).day)
            (period_start, _) = db.calcBillingPeriod(today)
            unbilled = db.getUnbilledHosts(period_start)  # 4 hosts from fixtures
            self.assertEqual(len(unbilled), 4)
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
            # Rollover enabled new counting method
            unbilled = db.getUnbilledHosts(period_start)  # Billed hosts cleared, all 5 are unbilled, but filtered to 4 by new counting
            self.assertEqual(len(unbilled), 4)

    def testMainAws(self):
        with self.settings(
            BILLING_INTERFACE=BILLING_INTERFACE_AWS,
            REGION_NAME="us-east-1",
            PRODUCT_CODE="aap-001",
        ):
            db.setDate(
                db.DateSettingEnum.INSTALL_DATE,
                datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            )
            today = datetime(2022, 2, 7, tzinfo=timezone.utc)
            (period_start, _) = db.calcBillingPeriod(today)
            unbilled = db.getUnbilledHosts(period_start)  # 4 hosts from fixtures
            self.assertEqual(len(unbilled), 4)
            with mock.patch(
                "botocore.client.BaseClient._make_api_call",
                new=mock_make_api_call,
            ):
                billing_record = awsapi.pegBillingCounter(settings.DIMENSION, unbilled)
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
                unbilled = db.getUnbilledHosts(period_start)  # Billed hosts cleared, all 5 are unbilled, but filtered to 4 by new counting
                self.assertEqual(len(unbilled), 4)

    def testHostsToReport(self):
        hosts = db.getUnbilledHosts(datetime(2021, 12, 31, tzinfo=timezone.utc))
        expectedUnbilled = ["host2", "host3", "host_alias_1", "host_alias_2"]
        self.assertEqual(len(hosts), 4)
        for host in hosts:
            self.assertIn(host, expectedUnbilled)

    def testMarkHostsBilled(self):
        hosts = db.getUnbilledHosts(datetime(2021, 12, 31, tzinfo=timezone.utc))
        db.markHostsBilled(hosts)
        for host in hosts:
            qs = BilledHost.objects.filter(host_name=host).order_by("-billed_date")
            self.assertTrue(qs.exists())
            self.assertEqual(qs.first().rollover_date, None)
        shouldbezero = db.getUnbilledHosts(datetime(2021, 12, 31, tzinfo=timezone.utc))
        self.assertEqual(len(shouldbezero), 0)

    def testSeedInstallDate(self):
        installDate = db.getDate(db.DateSettingEnum.INSTALL_DATE)
        self.assertEqual(installDate.date(), datetime.now(timezone.utc).date())

    def testBillingPeriodCalcAzure(self):
        with self.settings(BILLING_INTERFACE=BILLING_INTERFACE_AZURE):
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
                (period_start, period_end) = db.calcBillingPeriod(current_date=today)
                self.assertEqual(period_start.year, datum[3])
                self.assertEqual(period_start.month, datum[4])
                self.assertEqual(period_start.day, datum[5])
                self.assertEqual(period_end.year, datum[6])
                self.assertEqual(period_end.month, datum[7])
                self.assertEqual(period_end.day, datum[8])

    def testBillingPeriodCalcAws(self):
        with self.settings(
            BILLING_INTERFACE=BILLING_INTERFACE_AWS,
            REGION_NAME="us-east-1",
            PRODUCT_CODE="aap-001",
        ):
            # "today" is 1-15-2022
            # Install dates: Dec 1, 15, 31 2021
            # (inst date, exp start date, exp end date)
            today = datetime(2022, 1, 15, tzinfo=timezone.utc)
            data = [
                (2021, 12, 1, 2022, 1, 1, 2022, 1, 31),
                (2021, 12, 31, 2022, 1, 1, 2022, 1, 31),
            ]
            for datum in data:
                db.setDate(
                    db.DateSettingEnum.INSTALL_DATE,
                    datetime(datum[0], datum[1], datum[2], tzinfo=timezone.utc),
                )
                (period_start, period_end) = db.calcBillingPeriod(current_date=today)
                self.assertEqual(period_start.year, datum[3])
                self.assertEqual(period_start.month, datum[4])
                self.assertEqual(period_start.day, datum[5])
                self.assertEqual(period_end.year, datum[6])
                self.assertEqual(period_end.month, datum[7])
                self.assertEqual(period_end.day, datum[8])

    def testBillingPeriodSpecialAzure(self):
        with self.settings(BILLING_INTERFACE=BILLING_INTERFACE_AZURE):
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
                (period_start, period_end) = db.calcBillingPeriod(current_date=today)
                self.assertEqual(period_start.year, datum[3])
                self.assertEqual(period_start.month, datum[4])
                self.assertEqual(period_start.day, datum[5])
                self.assertEqual(period_end.year, datum[6])
                self.assertEqual(period_end.month, datum[7])
                self.assertEqual(period_end.day, datum[8])

    def testBillingPeriodSpecialAws(self):
        with self.settings(
            BILLING_INTERFACE=BILLING_INTERFACE_AWS,
            REGION_NAME="us-east-1",
            PRODUCT_CODE="aap-001",
        ):
            # Test february since it is short
            # Install dates: Dec 1, 15, 31 2021
            # (inst date, exp start date, exp end date)
            today = datetime(2022, 2, 15, tzinfo=timezone.utc)
            data = [
                (2021, 12, 1, 2022, 2, 1, 2022, 2, 28),
                (2021, 12, 31, 2022, 2, 1, 2022, 2, 28),
            ]
            for datum in data:
                db.setDate(
                    db.DateSettingEnum.INSTALL_DATE,
                    datetime(datum[0], datum[1], datum[2], tzinfo=timezone.utc),
                )
                (period_start, period_end) = db.calcBillingPeriod(current_date=today)
                self.assertEqual(period_start.year, datum[3])
                self.assertEqual(period_start.month, datum[4])
                self.assertEqual(period_start.day, datum[5])
                self.assertEqual(period_end.year, datum[6])
                self.assertEqual(period_end.month, datum[7])
                self.assertEqual(period_end.day, datum[8])

    @mock.patch("requests.get", side_effect=mocked_azure_apis)
    @mock.patch("requests.post", side_effect=mocked_azure_apis)
    def testBillingApiAzure(self, mock_get, mock_post):
        with self.settings(BILLING_INTERFACE=BILLING_INTERFACE_AZURE):
            today = datetime.now(timezone.utc)

            hosts = db.getUnbilledHosts(datetime(2021, 12, 31, tzinfo=timezone.utc))
            billing_data = azapi.pegBillingCounter(settings.DIMENSION, hosts)
            db.recordBillingInstance(billing_data)
            record = BillingRecord.objects.first()
            self.assertEqual(record.quantity, 4)
            self.assertEqual(record.billed_date.day, today.day)
            self.assertEqual(record.billed_date.month, today.month)
            self.assertEqual(record.billed_date.year, today.year)
            self.assertEqual(record.azure_status, "Accepted")
            self.assertEqual(record.azure_message_time.day, 12)
            self.assertEqual(record.azure_message_time.hour, 13)
            self.assertEqual(record.azure_effective_start_time.hour, 8)

    def testBillingApiAws(self):
        with self.settings(
            BILLING_INTERFACE=BILLING_INTERFACE_AWS,
            REGION_NAME="us-east-1",
            PRODUCT_CODE="aap-001",
        ):
            today = datetime.now(timezone.utc)
            hosts = db.getUnbilledHosts(datetime(2021, 12, 31, tzinfo=timezone.utc))
            with mock.patch(
                "botocore.client.BaseClient._make_api_call",
                new=mock_make_api_call,
            ):
                billing_data = awsapi.pegBillingCounter(settings.DIMENSION, hosts)
                db.recordBillingInstance(billing_data)
                record = BillingRecord.objects.first()
                self.assertEqual(record.quantity, 4)
                self.assertEqual(record.billed_date.day, today.day)
                self.assertEqual(record.billed_date.month, today.month)
                self.assertEqual(record.billed_date.year, today.year)

    # @mock.patch("requests.get", side_effect=mocked_storage_file)
    @mock.patch("builtins.open", side_effect=mocked_storage_file)
    def testBaseQuantity(self, mock_get):
        # Base quantity of 0 (from mock)
        res = cli.determineBaseQuantity("bhavensttest", "plan7")
        self.assertEqual(res, 0)

        with self.assertRaises(SystemExit):
            res = cli.determineBaseQuantity("offer", "plan")
            self.assertIsNone(res, msg="Base quantity should not exist")
        db.recordBaseQuantity("offer", "plan", 10)
        res = cli.determineBaseQuantity("offer", "plan")
        self.assertEqual(res, 10, msg="Base quantity did not match expected: %d" % res)
        with self.assertRaises(SystemExit):
            res = cli.determineBaseQuantity("offer", "plan2")
            self.assertIsNone(res, msg="Base quantity for plan2 should not exist.")
        with self.assertRaises(RuntimeError):
            db.recordBaseQuantity("bhavensttest", "plan7", 99)

    def testBillingThreshold(self):
        # Storage of hosts lower than billing threshold check
        period_start = datetime(2021, 12, 31, tzinfo=timezone.utc)
        processed_host_count = db.getProcessedHostCount(period_start)
        self.assertEqual(processed_host_count, 3)
        hosts = db.getUnbilledHosts(period_start)
        self.assertEqual(len(hosts), 4)
        # Bill all (base_quantity of 3)
        (hosts_to_bill, hosts_to_mark) = db.getHostsToBill(period_start, 3)
        self.assertEqual(len(hosts_to_bill), 4)
        self.assertEqual(len(hosts_to_mark), 0)
        # Bill none (base_quantity of 10)
        (hosts_to_bill, hosts_to_mark) = db.getHostsToBill(period_start, 10)
        self.assertEqual(len(hosts_to_bill), 0)
        self.assertEqual(len(hosts_to_mark), 4)
        # Bill part (base_quantity of 4)
        (hosts_to_bill, hosts_to_mark) = db.getHostsToBill(period_start, 4)
        self.assertEqual(len(hosts_to_bill), 3)
        self.assertEqual(len(hosts_to_mark), 1)

        # Base quantity of 0
        (hosts_to_bill, hosts_to_mark) = db.getHostsToBill(period_start, 0)
        self.assertEqual(len(hosts_to_bill), 4)
        self.assertEqual(len(hosts_to_mark), 0)

        db.markHostsSeen(hosts)
        hosts = db.getUnbilledHosts(period_start)
        self.assertEqual(len(hosts), 0)
        record = BilledHost.objects.first()
        self.assertFalse(record.reported)

        with self.settings(BILLING_INTERFACE=BILLING_INTERFACE_AZURE):
            # Ensure non-reported hosts will roll over
            db.rolloverIfNeeded()

            lastBilledHost = db.BilledHost.objects.first()
            today = datetime.now(timezone.utc)
            self.assertEqual(lastBilledHost.rollover_date.date(), today.date())

    def testNewCounting(self):
        with self.settings(BILLING_INTERFACE=BILLING_INTERFACE_AZURE):
            # Old counting
            period_start = datetime(2021, 12, 31, tzinfo=timezone.utc)
            hosts = db.getUnbilledHosts(period_start)
            self.assertEqual(len(hosts), 4)
            self.assertNotIn("real_host", hosts)
            self.assertIn("host_alias_1", hosts)

            db.rolloverIfNeeded()

            # New counting
            period_start = datetime(2021, 12, 31, tzinfo=timezone.utc)
            hosts = db.getUnbilledHosts(period_start)
            self.assertEqual(len(hosts), 4)
            self.assertIn("real_host", hosts)
            self.assertNotIn("host_alias_1", hosts)
