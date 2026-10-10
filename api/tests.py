from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from unittest.mock import patch
from decimal import Decimal
from datetime import timedelta
from api.models import BoostSubscription, UserCard, Wallet, WalletTransaction, IngestedJob
from django.core.management import call_command
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()


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
        # Create a subscription
        subscription = BoostSubscription.objects.create(
            user=self.user,
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
        # Setup expired but auto-renew subscription
        subscription = BoostSubscription.objects.create(
            user=self.user,
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
