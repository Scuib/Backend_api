"""Two-week free trial, granted to every user (new and existing).

The trial is stored as an ordinary :class:`~api.models.BoostSubscription` row
with ``plan="trial"`` rather than as a separate model, so every existing
entitlement check::

    BoostSubscription.objects.filter(user=user, active=True, end_date__gte=now)

picks it up with no change at the call site.

Rules
-----
* 14 days from now.
* ``auto_renew=False`` — a trial must never reach the Paystack charge path in
  the ``renew_subscriptions`` command (which filters on ``auto_renew=True``),
  so it expires quietly with no card and no renewal-failure email.
* Re-granting overwrites an existing paid subscription (deliberate product
  decision), but never shortens a trial that is still running, so running the
  grant twice cannot hand out extra days.
"""

import logging
import time
from datetime import timedelta

import resend
from django.conf import settings
from django.template.loader import get_template
from django.utils import timezone

from .models import BoostSubscription, User

logger = logging.getLogger(__name__)

TRIAL_PLAN = BoostSubscription.TRIAL_PLAN
TRIAL_DAYS = BoostSubscription.TRIAL_DAYS

TRIAL_EMAIL_SUBJECT = "Your 2-week free trial has started"
TRIAL_EMAIL_FROM = "Scuibai <godwin@scuib.com>"


def start_free_trial(user):
    """Grant (or re-grant) the free trial. Returns the subscription row."""
    now = timezone.now()
    end_date = now + timedelta(days=TRIAL_DAYS)

    subscription, created = BoostSubscription.objects.get_or_create(
        user=user,
        defaults={
            "plan": TRIAL_PLAN,
            "start_date": now,
            "end_date": end_date,
            "active": True,
            "auto_renew": False,
        },
    )
    if created:
        return subscription

    # Already running a trial: leave the clock alone.
    if (
        subscription.plan == TRIAL_PLAN
        and subscription.active
        and subscription.end_date > now
    ):
        return subscription

    # Anything else (paid plan, expired sub) is replaced by the trial.
    subscription.plan = TRIAL_PLAN
    subscription.start_date = now
    subscription.end_date = end_date
    subscription.active = True
    subscription.auto_renew = False
    subscription.save()
    return subscription


def send_trial_started_email(user, subscription=None):
    """Send the trial-start email. Best-effort and never raises.

    An email failure must not break registration or a management command, so
    every error is logged and swallowed.

    Returns True when the email was sent (and ``trial_notified_at`` stamped).
    """
    try:
        subscription = subscription or BoostSubscription.objects.filter(
            user=user
        ).first()
        if subscription is None:
            logger.warning("No subscription for %s; skipping trial email", user.email)
            return False

        html = get_template("trial/free_trial_started.html").render(
            {
                "user": user,
                "subscription": subscription,
                "expires": subscription.end_date,
                "trial_days": TRIAL_DAYS,
            }
        )

        resend.api_key = settings.NEW_RESEND_API_KEY
        params: resend.Emails.SendParams = {
            "from": TRIAL_EMAIL_FROM,
            "to": [user.email],
            "subject": TRIAL_EMAIL_SUBJECT,
            "html": html,
        }
        resend.Emails.send(params)

        subscription.trial_notified_at = timezone.now()
        subscription.save(update_fields=["trial_notified_at"])
        return True
    except Exception as exc:
        logger.warning(
            "Failed to send trial email to %s: %s",
            getattr(user, "email", user),
            exc,
        )
        return False


def sync_trials(*, dry_run=False, limit=0, delay=0.1):
    """Backfill missing trials and email everyone not yet notified.

    Idempotent and safe to call repeatedly — it is the single implementation
    behind both the ``sync_free_trials`` management command and the admin
    endpoint, which is the production path (Render's free tier has no shell,
    so a command cannot be run against the live database).

    * grants a trial only to users with no subscription row at all, covering
      anyone who registered during the deploy window (after migration 0007
      ran but before the new code served traffic);
    * emails only subscriptions whose ``trial_notified_at`` is still null and
      whose trial is still running — expired trials are counted but skipped.

    ``limit``/``delay`` exist to keep a single call short and inside Resend's
    rate limit; when ``remaining`` is not 0, simply call again.

    Returns a summary dict::

        dry_run         nothing was changed or sent
        missing         users with no subscription row at all
        granted         rows created (always 0 on a dry run)
        pending         emails owed before this call
        selected        rows this call handled (after ``limit``)
        emailed         emails sent by this call
        failed          sends that raised — still owed, retried next call
        expired_skipped expired trials that will never be emailed
        remaining       emails still owed after this call
    """
    now = timezone.now()

    # 1. Users with no subscription row at all.
    missing_qs = User.objects.exclude(
        id__in=BoostSubscription.objects.values_list("user_id", flat=True)
    )
    missing = missing_qs.count()
    granted = 0
    if not dry_run and missing:
        for user in missing_qs.iterator():
            start_free_trial(user)
            granted += 1

    # 2. Trials that still need their start email. Evaluated *after* the
    #    grants above, so freshly granted users are eligible in the same call.
    pending_qs = (
        BoostSubscription.objects.filter(
            plan=TRIAL_PLAN,
            trial_notified_at__isnull=True,
            end_date__gte=now,
        )
        .select_related("user")
        .order_by("id")
    )
    expired_skipped = BoostSubscription.objects.filter(
        plan=TRIAL_PLAN,
        trial_notified_at__isnull=True,
        end_date__lt=now,
    ).count()

    pending = pending_qs.count()
    to_send = list(pending_qs[:limit] if limit else pending_qs)

    emailed = 0
    failed = 0
    if not dry_run:
        for subscription in to_send:
            if send_trial_started_email(
                subscription.user, subscription=subscription
            ):
                emailed += 1
            else:
                failed += 1
            if delay:
                time.sleep(delay)

    return {
        "dry_run": dry_run,
        "missing": missing,
        "granted": granted,
        "pending": pending,
        "selected": len(to_send),
        "emailed": emailed,
        "failed": failed,
        "expired_skipped": expired_skipped,
        "remaining": pending - emailed,
    }
