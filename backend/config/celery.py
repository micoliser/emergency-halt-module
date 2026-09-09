"""Celery app + beat schedule for the poll-and-diff indexer."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("emergency_halt")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **_kwargs) -> None:
    from django.conf import settings

    sender.add_periodic_task(
        float(settings.SYNC_POLL_INTERVAL_SECONDS),
        sender.signature("apps.sync.tasks.poll_and_diff"),
        name="poll-and-diff halt module",
    )


@app.task(name="config.debug_task")
def debug_task() -> str:
    """Smoke task: `celery -A config call config.debug_task`."""
    return "ok"
