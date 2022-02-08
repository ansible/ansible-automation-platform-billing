from django.db import models


class BilledHost(models.Model):
    """
    Storage for billed hosts, retaining hostname and dates.
    """

    class Meta:
        app_label = "billing"
        verbose_name_plural = "billed hosts"
        ordering = ("-pk",)

    billed_date = models.DateTimeField()

    host_name = models.CharField(
        max_length=1024,
        primary_key=True,
    )

    rollover_date = models.DateTimeField(default=None, null=True)


class BillingRecord(models.Model):
    """
    Creates a record of every billing counter "hit".
    """

    class Meta:
        app_label = "billing"
        verbose_name_plural = "billing records"
        ordering = ("-pk",)

    billed_date = models.DateTimeField()

    dimension = models.CharField(
        max_length=1024,
    )

    quantity = models.IntegerField()

    hosts = models.CharField(
        max_length=1024,
    )

    managed_app_id = models.CharField(
        max_length=1024,
    )

    resource_id = models.CharField(
        max_length=1024,
    )

    plan = models.CharField(
        max_length=1024,
    )

    usage_event_id = models.CharField(
        max_length=1024,
    )


class InstallDate(models.Model):
    """
    Record installation date of managed app.
    """

    install_date = models.DateTimeField(default=None)


class RolloverDate(models.Model):
    """
    Record calculated billing period rollover date.
    """

    rollover_date = models.DateTimeField(default=None)
