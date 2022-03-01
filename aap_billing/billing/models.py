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

    host_name = models.CharField(max_length=1024)

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


class DateSetting(models.Model):
    """
    Store important dates
    """

    class Meta:
        app_label = "billing"
        verbose_name_plural = "date settings"
        ordering = ("-pk",)

    name = models.CharField(max_length=1024, primary_key=True)

    date = models.DateTimeField()
