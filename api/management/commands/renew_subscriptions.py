import requests
from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
import uuid
import resend
from django.conf import settings
from api.models import BoostSubscription, UserCard, Wallet, WalletTransaction


class Command(BaseCommand):
    help = "Renew expired boost subscriptions using saved user cards via Paystack"

    def handle(self, *args, **options):
        now = timezone.now()
        # Find active subscriptions that have expired
        expired_subs = BoostSubscription.objects.filter(
            active=True,
            auto_renew=True,
            end_date__lte=now
        )

        self.stdout.write(f"Found {expired_subs.count()} expired subscriptions for renewal.")

        PRICES = {
            "daily": Decimal("200"),
            "weekly": Decimal("100"),
            "monthly": Decimal("4000"),
        }

        DURATIONS = {
            "daily": 1,
            "weekly": 7,
            "monthly": 30,
        }

        for sub in expired_subs:
            user = sub.user
            plan = sub.plan

            if plan not in PRICES:
                self.stderr.write(f"Invalid plan '{plan}' for user {user.email}. Disabling subscription.")
                sub.active = False
                sub.save()
                continue

            cost = PRICES[plan]
            duration = DURATIONS[plan]

            # Find an active saved card for the user
            card = UserCard.objects.filter(user=user, is_active=True).first()

            if not card:
                self.stderr.write(f"No active card found for user {user.email}. Disabling subscription.")
                sub.active = False
                sub.save()
                self.notify_failure(user, plan, "No saved payment card found.")
                continue

            # Charge the card via Paystack Charge Authorization API
            success, error_msg = self.charge_saved_card(user, card, cost, plan)

            if success:
                # Extend subscription
                sub.start_date = now
                sub.end_date = now + timedelta(days=duration)
                sub.active = True
                sub.save()
                self.stdout.write(f"Successfully renewed subscription for {user.email} (Plan: {plan}).")
            else:
                # Disable subscription and notify
                sub.active = False
                sub.save()
                self.stderr.write(f"Failed to charge user {user.email} card: {error_msg}. Disabling subscription.")
                self.notify_failure(user, plan, error_msg)

    def charge_saved_card(self, user, card, cost, plan) -> tuple[bool, str]:
        """
        Attempts to charge the user's card. Returns (success, error_message).
        """
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }

        amount_in_kobo = int(cost * 100)
        reference = f"renew_{uuid.uuid4().hex[:12]}"

        payload = {
            "email": user.email,
            "amount": amount_in_kobo,
            "authorization_code": card.authorization_code,
            "reference": reference,
        }

        try:
            response = requests.post(
                "https://api.paystack.co/transaction/charge_authorization",
                json=payload,
                headers=headers,
                timeout=15
            )
            result = response.json()

            if result.get("status") is True and result.get("data", {}).get("status") == "success":
                # Create transactions to represent funding and subscription cost deduction
                wallet, _ = Wallet.objects.get_or_create(user=user)

                # Fund Wallet
                wallet.balance += cost
                wallet.save()

                WalletTransaction.objects.create(
                    wallet=wallet,
                    amount=cost,
                    type="deposit",
                    reference=reference,
                    status="success",
                    source="card",
                    description=f"Auto-funding via saved card for {plan} subscription"
                )

                # Deduct from Wallet for Subscription
                wallet.balance -= cost
                wallet.save()

                WalletTransaction.objects.create(
                    wallet=wallet,
                    amount=cost,
                    type="withdrawal",
                    reference=f"sub_{reference}",
                    status="success",
                    source="wallet",
                    description=f"Deduction for Boost {plan} subscription renewal"
                )

                return True, ""
            else:
                error_msg = result.get("data", {}).get("gateway_response") or result.get("message") or "Charge failed"
                return False, error_msg

        except Exception as e:
            return False, str(e)

    def notify_failure(self, user, plan, reason):
        """
        Sends an email notifying the user of subscription renewal failure.
        """
        resend.api_key = settings.NEW_RESEND_API_KEY
        subject = "Subscription Renewal Failed"
        html = f"""
        <div style="font-family: sans-serif; padding: 20px; max-width: 600px; margin: 0 auto; border: 1px solid #eee; border-radius: 8px;">
            <h2 style="color: #d9534f;">Your Subscription Renewal Failed</h2>
            <p>Hello {user.first_name or 'there'},</p>
            <p>We attempted to automatically renew your <strong>{plan.capitalize()}</strong> Boost Subscription, but the payment failed.</p>
            <p><strong>Reason:</strong> {reason}</p>
            <p>As a result, your subscription features have been deactivated. To reactivate, please log in and update your billing details.</p>
            <p>Best regards,<br>The Scuib Team</p>
        </div>
        """
        params: resend.Emails.SendParams = {
            "from": "Scuibai <godwin@scuib.com>",
            "to": [user.email],
            "subject": subject,
            "html": html,
        }
        try:
            resend.Emails.send(params)
            self.stdout.write(f"Sent failure email to {user.email}")
        except Exception as e:
            self.stderr.write(f"Failed to send failure email to {user.email}: {e}")
