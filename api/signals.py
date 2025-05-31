# from django.shortcuts import get_object_or_404, get_list_or_404
from django.db.models.signals import post_save, post_delete
from django.shortcuts import get_object_or_404
from django.db import transaction

from .models import (
    User,
    Profile,
    Wallet,
    CompanyProfile,
)
from django.dispatch import receiver
from scuibai.settings import BASE_DIR
from .models import Message
import resend


from .custom_signal import job_created


@receiver(post_save, sender=User)
def create_user_signals(sender, instance, created, **kwargs):
    """
    Create a Profile when:
    1. User was previously a company (or undecided) and is now NOT a company (company=False).
    2. Profile does not already exist.
    """
    if created:
        return
    if instance.company is False and not Profile.objects.filter(user=instance).exists():
        Profile.objects.create(user=instance)

        return "Profile created"
    return


@receiver(post_save, sender=User)
def create_company_signals(sender, instance, created, **kwargs):
    """
    Create a CompanyProfile when:
    1. User was previously NOT a company (or undecided) and now sets company=True.
    2. CompanyProfile does not already exist.
    """
    if created:
        return  # Do nothing at registration

    # Check if company field changed to True
    if (
        instance.company is True
        and not CompanyProfile.objects.filter(owner=instance).exists()
    ):
        CompanyProfile.objects.create(owner=instance)


@receiver(post_save, sender=Message)
def send_message_email(sender, instance, created, **kwargs):
    if created:
        recipient = instance.user
        sender_user = instance.sender
        message = instance.content

        try:
            wallet = Wallet.objects.select_for_update().get(user=recipient)
        except Wallet.DoesNotExist:
            wallet = None

        # Auto-unlock logic
        if wallet and wallet.balance >= 100:
            with transaction.atomic():
                # Deduct amount
                wallet.balance -= 100
                wallet.save()

                # Unlock message
                instance.unlocked = True
                instance.save(update_fields=["unlocked"])

            preview = message
        else:
            preview = "You’ve received a message. Pay ₦100 to view full content."

        email_html = f"""
            <p>Hi {recipient.first_name},</p>
            <p>{sender_user.first_name} has shared a job opportunity with you.</p>
            <p><strong>Message:</strong><br>{preview}</p>
            <br>
            <p>Log in to your account to respond or top up your wallet.</p>
            <p>Best,<br>Scuibai Team</p>
        """

        subject = instance.title
        try:
            resend.Emails.send(
                {
                    "from": "Scuibai <Admin@scuib.com>",
                    "to": [recipient.email],
                    "subject": subject,
                    "html": email_html,
                }
            )
        except Exception as e:
            print(f"Failed to send email to {recipient.email}: {str(e)}")


@receiver(post_save, sender=User)
def create_user_wallet(sender, instance, created, **kwargs):
    if created:
        Wallet.objects.create(user=instance)
