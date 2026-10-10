"""Grant the 14-day free trial to every user that already exists.

Runs once during deploy — Render's ``buildCommand`` runs ``migrate``.

Emails are deliberately *not* sent from here: an HTTP call to Resend per user
inside a migration is slow and can fail the whole deploy. The
``sync_free_trials`` command sends them (and catches anyone registered during
the deploy window).
"""

from datetime import timedelta

from django.db import migrations
from django.utils import timezone

TRIAL_PLAN = "trial"
TRIAL_DAYS = 14


def grant_free_trials(apps, schema_editor):
    BoostSubscription = apps.get_model("api", "BoostSubscription")
    User = apps.get_model("api", "User")

    now = timezone.now()
    end_date = now + timedelta(days=TRIAL_DAYS)

    # 1. Existing subscription rows move onto the trial. This deliberately
    #    includes currently paying subscribers: plan and end_date are
    #    overwritten, and auto_renew is switched off so nobody is charged.
    BoostSubscription.objects.all().update(
        plan=TRIAL_PLAN,
        start_date=now,
        end_date=end_date,
        active=True,
        auto_renew=False,
        trial_notified_at=None,
    )

    # 2. Users without a subscription row get one.
    already_subscribed = list(
        BoostSubscription.objects.values_list("user_id", flat=True)
    )
    missing_ids = User.objects.exclude(id__in=already_subscribed).values_list(
        "id", flat=True
    )
    BoostSubscription.objects.bulk_create(
        [
            BoostSubscription(
                user_id=user_id,
                plan=TRIAL_PLAN,
                start_date=now,
                end_date=end_date,
                active=True,
                auto_renew=False,
            )
            for user_id in missing_ids
        ],
        batch_size=500,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0006_boostsubscription_trial_notified_at_and_more"),
    ]

    operations = [
        # Reverse is a no-op on purpose: the paid subscriptions this overwrote
        # cannot be reconstructed. Rolling back simply stops here and lets the
        # trials lapse on their own rather than deactivating people who were
        # already paying before the feature landed.
        migrations.RunPython(grant_free_trials, migrations.RunPython.noop),
    ]
