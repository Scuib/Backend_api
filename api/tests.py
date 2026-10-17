from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from unittest.mock import patch
from decimal import Decimal
from datetime import timedelta
from api.models import BoostSubscription, UserCard, Wallet, WalletTransaction, IngestedJob
from api.free_trial import start_free_trial
from django.core.management import call_command
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()


def _set_subscription(user, **fields):
    """Adjust the subscription a user already has.

    Every user is now given a trial row on creation (post_save signal), and
    BoostSubscription is a OneToOneField — so tests mutate that row rather
    than creating a second one.
    """
    subscription = BoostSubscription.objects.get(user=user)
    for key, value in fields.items():
        setattr(subscription, key, value)
    subscription.save()
    return subscription


class SubscriptionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@scuib.com",
            password="testpassword",
            first_name="Test"
        )
        self.wallet, _ = Wallet.objects.get_or_create(user=self.user, defaults={"balance": Decimal("0.00")})
        # Generate JWT Token for authorization header
        self.token = str(AccessToken.for_user(self.user))
        self.auth_headers = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    def test_verify_payment_saves_card(self):
        # Create a pending wallet transaction to match the payment
        reference = "pay_123456"
        WalletTransaction.objects.create(
            wallet=self.wallet,
            amount=Decimal("1000"),
            type="deposit",
            reference=reference,
            status="pending"
        )

        mock_paystack_response = {
            "status": True,
            "data": {
                "status": "success",
                "amount": 100000,  # 1000 Naira in kobo
                "authorization": {
                    "authorization_code": "AUTH_card123",
                    "bin": "408408",
                    "last4": "1234",
                    "exp_month": "12",
                    "exp_year": "2030",
                    "channel": "card",
                    "card_type": "visa",
                    "bank": "Test Bank",
                    "reusable": True,
                    "signature": "SIG_signature123"
                }
            }
        }

        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = mock_paystack_response
            response = self.client.get(reverse("verify_payment", args=[reference]), **self.auth_headers)
            self.assertEqual(response.status_code, 200)

        # Verify wallet balance was updated
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("1000.00"))

        # Verify card was saved
        card = UserCard.objects.filter(user=self.user).first()
        self.assertIsNotNone(card)
        self.assertEqual(card.authorization_code, "AUTH_card123")
        self.assertEqual(card.last4, "1234")
        self.assertTrue(card.is_active)

    def test_list_and_delete_cards(self):
        # Create user cards
        card = UserCard.objects.create(
            user=self.user,
            authorization_code="AUTH_card123",
            last4="1234",
            brand="visa",
            is_active=True
        )

        # Test listing saved cards
        response = self.client.get(reverse("subscription-cards"), **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["last4"], "1234")

        # Test deleting a saved card
        delete_url = reverse("delete-card", args=[card.id])
        response = self.client.delete(delete_url, **self.auth_headers)
        self.assertEqual(response.status_code, 200)

        # Verify card is deactivated
        card.refresh_from_db()
        self.assertFalse(card.is_active)

    def test_toggle_auto_renew(self):
        # Switch the trial the user was given at signup over to a paid plan
        subscription = _set_subscription(
            self.user,
            plan="monthly",
            end_date=timezone.now() + timedelta(days=30),
            active=True,
            auto_renew=True
        )

        response = self.client.post(
            reverse("toggle-auto-renew"),
            data={},
            content_type="application/json",
            **self.auth_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["auto_renew"])

        subscription.refresh_from_db()
        self.assertFalse(subscription.auto_renew)

    @patch("requests.post")
    @patch("resend.Emails.send")
    def test_renew_subscription_command(self, mock_send_email, mock_post):
        # Expired but auto-renew subscription (converted from the signup trial)
        subscription = _set_subscription(
            self.user,
            plan="monthly",
            end_date=timezone.now() - timedelta(minutes=5),  # expired
            active=True,
            auto_renew=True
        )

        # Setup card for billing
        card = UserCard.objects.create(
            user=self.user,
            authorization_code="AUTH_card123",
            last4="1234",
            brand="visa",
            is_active=True
        )

        # 1. Test successful renewal
        mock_paystack_response = {
            "status": True,
            "data": {
                "status": "success",
                "amount": 400000,
                "reference": "ref_renew_test"
            }
        }
        mock_post.return_value.json.return_value = mock_paystack_response

        call_command("renew_subscriptions")

        subscription.refresh_from_db()
        self.assertTrue(subscription.active)
        self.assertGreater(subscription.end_date, timezone.now())

        # 2. Test failed renewal
        subscription.end_date = timezone.now() - timedelta(minutes=5)
        subscription.active = True
        subscription.save()

        mock_paystack_failed_response = {
            "status": False,
            "message": "Insufficient funds"
        }
        mock_post.return_value.json.return_value = mock_paystack_failed_response

        call_command("renew_subscriptions")

        subscription.refresh_from_db()
        self.assertFalse(subscription.active)
        mock_send_email.assert_called_once()


class FreeTrialTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="trial@scuib.com",
            password="testpassword",
            first_name="Trial"
        )
        self.token = str(AccessToken.for_user(self.user))
        self.auth_headers = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    def _entitlement_filter(self):
        # The exact expression the boost-chat gates use.
        return BoostSubscription.objects.filter(
            user=self.user, active=True, end_date__gte=timezone.now()
        )

    def test_new_user_is_given_a_14_day_trial(self):
        sub = BoostSubscription.objects.get(user=self.user)

        self.assertEqual(sub.plan, BoostSubscription.TRIAL_PLAN)
        self.assertTrue(sub.is_trial)
        self.assertTrue(sub.active)
        self.assertFalse(sub.auto_renew)  # a trial must never be charged
        self.assertTrue(sub.is_active())

        remaining = (sub.end_date - timezone.now()).total_seconds()
        self.assertAlmostEqual(remaining, 14 * 86400, delta=60)

    def test_trial_unlocks_the_existing_entitlement_check(self):
        self.assertTrue(self._entitlement_filter().exists())

        _set_subscription(self.user, end_date=timezone.now() - timedelta(minutes=1))

        self.assertFalse(self._entitlement_filter().exists())
        self.assertFalse(BoostSubscription.objects.get(user=self.user).is_active())

    def test_trial_overwrites_an_active_paid_subscription(self):
        _set_subscription(
            self.user,
            plan="monthly",
            end_date=timezone.now() + timedelta(days=30),
            auto_renew=True,
        )

        sub = start_free_trial(self.user)

        self.assertEqual(sub.plan, "trial")
        self.assertFalse(sub.auto_renew)
        self.assertTrue(sub.active)
        remaining = (sub.end_date - timezone.now()).total_seconds()
        self.assertAlmostEqual(remaining, 14 * 86400, delta=60)

    def test_regranting_does_not_extend_a_running_trial(self):
        first_end = start_free_trial(self.user).end_date

        second = start_free_trial(self.user)

        self.assertEqual(second.end_date, first_end)

    def test_subscription_status_reports_the_trial(self):
        response = self.client.get(
            reverse("subscription-status"), **self.auth_headers
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["active"])
        self.assertTrue(response.data["is_trial"])
        self.assertEqual(response.data["plan"], "trial")
        self.assertFalse(response.data["auto_renew"])

    @patch("requests.post")
    @patch("resend.Emails.send")
    def test_expired_trial_is_never_charged_or_emailed(
        self, mock_send_email, mock_post
    ):
        _set_subscription(self.user, end_date=timezone.now() - timedelta(minutes=5))

        call_command("renew_subscriptions")

        mock_post.assert_not_called()
        mock_send_email.assert_not_called()

        sub = BoostSubscription.objects.get(user=self.user)
        self.assertTrue(sub.active)      # left untouched
        self.assertFalse(sub.is_active())  # but grants nothing

    @patch("resend.Emails.send")
    def test_sync_free_trials_emails_each_user_once(self, mock_send):
        call_command("sync_free_trials", delay=0)

        self.assertEqual(mock_send.call_count, 1)
        sub = BoostSubscription.objects.get(user=self.user)
        self.assertIsNotNone(sub.trial_notified_at)

        call_command("sync_free_trials", delay=0)

        self.assertEqual(mock_send.call_count, 1)  # not emailed twice

    @patch("resend.Emails.send")
    def test_sync_free_trials_dry_run_sends_nothing(self, mock_send):
        call_command("sync_free_trials", dry_run=True, delay=0)

        mock_send.assert_not_called()
        sub = BoostSubscription.objects.get(user=self.user)
        self.assertIsNone(sub.trial_notified_at)

    # --- the endpoint (this is what production actually calls) ----------

    def _staff_headers(self, email="admin@scuib.com"):
        """A staff account, with its own trial marked as already notified.

        Marking it keeps the pending counts in these tests down to the users
        they are actually about.
        """
        admin = User.objects.create_user(
            email=email, first_name="Admin"
        )
        admin.is_staff = True
        admin.save(update_fields=["is_staff"])
        BoostSubscription.objects.filter(user=admin).update(
            trial_notified_at=timezone.now()
        )
        token = str(AccessToken.for_user(admin))
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_sync_endpoint_rejects_anyone_who_is_not_staff(self):
        url = reverse("subscription-sync-trials")

        # No credentials at all -> 401 (JWTAuthentication supplies a
        # WWW-Authenticate header); a real user without is_staff -> 403.
        self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.get(url, **self.auth_headers).status_code, 403)
        self.assertEqual(self.client.post(url, **self.auth_headers).status_code, 403)

    @patch("resend.Emails.send")
    def test_sync_endpoint_get_is_always_a_dry_run(self, mock_send):
        headers = self._staff_headers()

        response = self.client.get(reverse("subscription-sync-trials"), **headers)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["dry_run"])
        self.assertEqual(response.data["granted"], 0)
        self.assertEqual(response.data["emailed"], 0)
        self.assertEqual(response.data["pending"], 1)
        mock_send.assert_not_called()
        self.assertIsNone(
            BoostSubscription.objects.get(user=self.user).trial_notified_at
        )

    @patch("resend.Emails.send")
    def test_sync_endpoint_post_sends_the_backfill(self, mock_send):
        headers = self._staff_headers()

        response = self.client.post(reverse("subscription-sync-trials"), **headers)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["dry_run"])
        self.assertEqual(response.data["missing"], 0)
        self.assertEqual(response.data["granted"], 0)
        self.assertEqual(response.data["emailed"], 1)
        self.assertEqual(response.data["failed"], 0)
        self.assertEqual(response.data["remaining"], 0)
        self.assertEqual(response.data["detail"], "All caught up.")
        mock_send.assert_called_once()
        self.assertIsNotNone(
            BoostSubscription.objects.get(user=self.user).trial_notified_at
        )

    @patch("resend.Emails.send")
    def test_sync_endpoint_grants_users_who_have_no_row(self, mock_send):
        # Simulates an account created during the deploy window: migration
        # 0007 had already run, so it never received a trial.
        headers = self._staff_headers()
        BoostSubscription.objects.filter(user=self.user).delete()

        response = self.client.post(reverse("subscription-sync-trials"), **headers)

        self.assertEqual(response.data["missing"], 1)
        self.assertEqual(response.data["granted"], 1)
        self.assertEqual(response.data["emailed"], 1)
        mock_send.assert_called_once()
        self.assertEqual(
            BoostSubscription.objects.get(user=self.user).plan, "trial"
        )

    @patch("resend.Emails.send")
    def test_sync_endpoint_repeats_only_do_what_is_still_owed(self, mock_send):
        headers = self._staff_headers()
        url = reverse("subscription-sync-trials")

        first = self.client.post(url, **headers)
        second = self.client.post(url, **headers)

        self.assertEqual(first.data["emailed"], 1)
        self.assertEqual(second.data["emailed"], 0)
        self.assertEqual(second.data["remaining"], 0)
        self.assertEqual(second.data["detail"], "All caught up.")
        self.assertEqual(mock_send.call_count, 1)

    @patch("resend.Emails.send")
    def test_sync_endpoint_batches_with_limit(self, mock_send):
        headers = self._staff_headers()
        for index in range(2):
            User.objects.create_user(
                email=f"batch{index}@scuib.com", first_name="Batch"
            )
        url = reverse("subscription-sync-trials")

        first = self.client.post(f"{url}?limit=2", **headers)
        second = self.client.post(f"{url}?limit=2", **headers)

        self.assertEqual(first.data["emailed"], 2)
        self.assertEqual(first.data["remaining"], 1)
        self.assertIn("call again", first.data["detail"])
        self.assertEqual(second.data["emailed"], 1)
        self.assertEqual(second.data["remaining"], 0)
        self.assertEqual(mock_send.call_count, 3)

    def test_swagger_documents_the_endpoint(self):
        # Guards the drf_yasg decorators: a malformed one breaks schema
        # generation, and that would otherwise only surface when someone
        # opens /swagger/.
        response = self.client.get("/swagger/?format=openapi")
        self.assertEqual(response.status_code, 200)

        path = "/api/subscription/sync-trials/"
        schema = response.json()
        self.assertIn(path, schema["paths"])
        methods = schema["paths"][path]
        self.assertIn("get", methods)
        self.assertIn("post", methods)


class DeleteOldIngestedJobsTests(TestCase):
    def _make_job(self, source_job_id, created_at):
        job = IngestedJob.objects.create(
            source_job_id=source_job_id,
            title=f"Job {source_job_id}",
            source="scuib_jobs_ai",
        )
        # created_at is auto_now_add, so backdate with a queryset update.
        IngestedJob.objects.filter(id=job.id).update(created_at=created_at)
        job.refresh_from_db()
        return job

    def test_deletes_only_jobs_older_than_7_days(self):
        now = timezone.now()
        old_job = self._make_job("old-job", now - timedelta(days=8))
        edge_job = self._make_job("edge-job", now - timedelta(days=7, hours=1))
        recent_job = self._make_job("recent-job", now - timedelta(days=6))

        url = reverse("delete-old-ingested-jobs")
        response = self.client.delete(url)  # AllowAny — no auth header needed
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["retention_days"], 7)
        self.assertEqual(response.data["deleted_jobs"], 2)

        remaining = set(IngestedJob.objects.values_list("source_job_id", flat=True))
        self.assertEqual(remaining, {"recent-job"})
        self.assertFalse(IngestedJob.objects.filter(id=old_job.id).exists())
        self.assertFalse(IngestedJob.objects.filter(id=edge_job.id).exists())
        self.assertTrue(IngestedJob.objects.filter(id=recent_job.id).exists())

    def test_noop_when_nothing_expired(self):
        self._make_job("fresh-job", timezone.now())

        url = reverse("delete-old-ingested-jobs")
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["deleted_jobs"], 0)
        self.assertEqual(IngestedJob.objects.count(), 1)
