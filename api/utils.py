from django.core.cache import cache
from django.utils.timezone import now
from datetime import timedelta
from .models import Jobs, Message


def cleanup_messages():
    last_cleanup = cache.get("last_message_cleanup")
    if not last_cleanup or (now() - last_cleanup).days >= 1:
        threshold = now() - timedelta(days=3)
        deleted_count, _ = Message.objects.filter(created_at__lt=threshold).delete()
        cache.set("last_message_cleanup", now(), timeout=86400)  # cache for 1 day
        return deleted_count
    return 0


def cleanup_old_jobs():
    """
    Delete job posts older than 3 days.
    Runs at most once per day (controlled with cache).
    """
    last_cleanup = cache.get("last_job_cleanup")
    if not last_cleanup or (now() - last_cleanup).days >= 1:
        threshold = now() - timedelta(days=3)
        deleted_count, _ = Jobs.objects.filter(created_at__lt=threshold).delete()
        cache.set("last_job_cleanup", now(), timeout=86400)  # 1 day cache
        return deleted_count
    return 0
