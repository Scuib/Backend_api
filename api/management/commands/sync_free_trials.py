"""Ensure every user has a free trial and email anyone not yet notified.

Thin wrapper around :func:`api.free_trial.sync_trials`, which is also what the
``/api/subscription/sync-trials/`` endpoint runs. **Production uses the
endpoint** — Render's free tier has no shell, so this command is for local
development and one-off use only.

Usage::

    python manage.py sync_free_trials --dry-run
    python manage.py sync_free_trials --limit 200
    python manage.py sync_free_trials
"""

from django.core.management.base import BaseCommand

from api.free_trial import sync_trials


class Command(BaseCommand):
    help = (
        "Grant the free trial to any user missing one, then send the "
        "trial-start email to everyone not yet notified. Idempotent. "
        "Prefer POST /api/subscription/sync-trials/ in production."
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
        summary = sync_trials(
            dry_run=options["dry_run"],
            limit=options["limit"],
            delay=options["delay"],
        )

        verb = "Would grant" if summary["dry_run"] else "Granted"
        self.stdout.write(
            f"{verb} a trial to {summary['missing']} user(s) with no subscription."
        )
        if summary["expired_skipped"]:
            self.stdout.write(
                f"Skipped {summary['expired_skipped']} already-expired trial(s)."
            )

        if summary["dry_run"]:
            self.stdout.write(
                f"Would email {summary['selected']} of {summary['pending']} "
                "pending user(s)."
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Emailed {summary['emailed']} user(s), "
                    f"{summary['failed']} failed, {summary['remaining']} left unsent."
                )
            )
