from django.core.cache import cache
from django.utils.timezone import now
from datetime import timedelta
from .models import Message


def cleanup_messages():
    last_cleanup = cache.get("last_message_cleanup")
    if not last_cleanup or (now() - last_cleanup).days >= 1:
        threshold = now() - timedelta(days=3)
        deleted_count, _ = Message.objects.filter(created_at__lt=threshold).delete()
        cache.set("last_message_cleanup", now(), timeout=86400)  # cache for 1 day
        return deleted_count
    return 0
