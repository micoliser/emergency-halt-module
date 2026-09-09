"""Single-row cursor recording what the indexer has seen on-chain."""

from django.db import models
from django.utils import timezone


class SyncCursor(models.Model):
    SINGLETON_ID = 1

    id = models.PositiveSmallIntegerField(primary_key=True, default=SINGLETON_ID)
    protocol_count = models.PositiveIntegerField(default=0)
    case_count = models.PositiveIntegerField(default=0)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    contract_address = models.CharField(max_length=42, blank=True, default="")

    class Meta:
        verbose_name = "sync cursor"
        verbose_name_plural = "sync cursor"

    def __str__(self) -> str:
        return (
            f"cursor protocols={self.protocol_count} cases={self.case_count} "
            f"last_success={self.last_success_at}"
        )

    def save(self, *args, **kwargs):
        self.id = self.SINGLETON_ID
        return super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "SyncCursor":
        cursor, _ = cls.objects.get_or_create(id=cls.SINGLETON_ID)
        return cursor

    def mark_success(self, **fields) -> None:
        now = timezone.now()
        for key, value in fields.items():
            setattr(self, key, value)
        self.last_run_at = now
        self.last_success_at = now
        self.last_error = ""
        self.save()

    def mark_error(self, message: str) -> None:
        self.last_run_at = timezone.now()
        self.last_error = str(message)[:2000]
        self.save()
