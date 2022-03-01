from django.db import models
import logging

logger = logging.getLogger()


class JobHostSummary(models.Model):
    """
    Adapted from http://github.com/ansible/awx
    Used for read-only access to main_jobhostsummary table
    """

    class Meta:
        app_label = "main"
        verbose_name_plural = "job host summaries"
        ordering = ("-pk",)
        managed = False

    created = models.DateTimeField()

    modified = models.DateTimeField()

    job_id = models.PositiveIntegerField()

    host_id = models.PositiveIntegerField()

    host_name = models.CharField(
        max_length=1024,
    )

    changed = models.PositiveIntegerField(default=0, editable=False)
    dark = models.PositiveIntegerField(default=0, editable=False)
    failures = models.PositiveIntegerField(default=0, editable=False)
    ignored = models.PositiveIntegerField(default=0, editable=False)
    ok = models.PositiveIntegerField(default=0, editable=False)
    processed = models.PositiveIntegerField(default=0, editable=False)
    rescued = models.PositiveIntegerField(default=0, editable=False)
    skipped = models.PositiveIntegerField(default=0, editable=False)
    failed = models.BooleanField(default=False, editable=False, db_index=True)

    def __str__(self):
        return "%s (modified: %s)" % (self.host_name, self.modified)

    def save(self, *args, **kwargs):
        logger.error("Job Host Summary table is read-only")
