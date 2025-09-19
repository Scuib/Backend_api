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
        teaser = message[:100]  # First 100 characters of the message
        preview = f"Preview: {teaser}... Pay ₦100 to view the full message."

        email_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; font-size: 14px; color: #333;">
            <p>Hi {recipient.first_name},</p>

            <p>{sender_user.first_name} has shared a job opportunity with you.</p>

            <p><strong>Message:</strong><br>{preview}</p>

            <p>
            Log in to your account to view the full message and respond.
            <br><br>
            If you have any questions, feel free to contact support.
            </p>

            <p>Best regards,<br>Scuibai Team</p>
        </body>
        </html>
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
