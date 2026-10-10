"""Ensure every user has a free trial and email anyone not yet notified.

Idempotent and safe to re-run:

* grants a trial only to users with no subscription row at all (covers anyone
  who registered during the deploy window, after migration 0007 ran but
  before the new code was serving traffic);
* emails only subscriptions whose ``trial_notified_at`` is still null and
  whose trial is still running.

Usage::

    python manage.py sync_free_trials --dry-run
    python manage.py sync_free_trials --limit 200
    python manage.py sync_free_trials
"""

import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from api.free_trial import TRIAL_PLAN, send_trial_started_email, start_free_trial
from api.models import BoostSubscription, User


class Command(BaseCommand):
    help = (
        "Grant the free trial to any user missing one, then send the "
        "trial-start email to everyone not yet notified. Idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would happen without granting or sending.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Send at most N emails (0 = no limit).",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=0.1,
            help="Seconds to wait between emails, to stay under rate limits.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]
        delay = options["delay"]
        now = timezone.now()

        # 1. Users with no subscription row at all.
        missing = User.objects.exclude(
            id__in=BoostSubscription.objects.values_list("user_id", flat=True)
        )
        missing_count = missing.count()
        if dry_run:
            self.stdout.write(
                f"Would grant a trial to {missing_count} user(s) with no subscription."
            )
        else:
            for user in missing.iterator():
                start_free_trial(user)
            self.stdout.write(f"Granted a trial to {missing_count} user(s).")

        # 2. Trials that still need their start email.
        pending = (
            BoostSubscription.objects.filter(
                plan=TRIAL_PLAN,
                trial_notified_at__isnull=True,
                end_date__gte=now,
            )
            .select_related("user")
            .order_by("id")
        )
        expired_unnotified = (
            BoostSubscription.objects.filter(
                plan=TRIAL_PLAN,
                trial_notified_at__isnull=True,
                end_date__lt=now,
            ).count()
        )
        if expired_unnotified:
            self.stdout.write(
                f"Skipping {expired_unnotified} already-expired trial(s)."
            )

        total = pending.count()
        to_send = pending[:limit] if limit else pending

        if dry_run:
            self.stdout.write(f"Would email {len(to_send)} of {total} pending user(s).")
            return

        sent = 0
        failed = 0
        for subscription in to_send:
            if send_trial_started_email(
                subscription.user, subscription=subscription
            ):
                sent += 1
            else:
                failed += 1
            if delay:
                time.sleep(delay)

        self.stdout.write(
            self.style.SUCCESS(f"Emailed {sent} user(s), {failed} failed, {total - len(to_send)} left unsent.")
        )
