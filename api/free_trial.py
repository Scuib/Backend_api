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
from datetime import timedelta

import resend
from django.conf import settings
from django.template.loader import get_template
from django.utils import timezone

from .models import BoostSubscription

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
