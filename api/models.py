from os import name
from unicodedata import category
from django.db import models, transaction
from django.contrib.auth.models import AbstractUser, PermissionsMixin
from django.urls import translate_url
from django.utils.translation import gettext_lazy as _
import uuid
from decimal import Decimal
from .managers import CustomUserManager
from cloudinary.models import CloudinaryField


class User(AbstractUser):
    AUTH_PROVIDERS = [
        ("email", "Email"),
        ("google", "Google"),
    ]

    email = models.EmailField(unique=True)
    username = models.CharField(max_length=100, blank=True, null=True)
    first_name = models.CharField(_("First Name"), max_length=100)
    last_name = models.CharField(_("Last Name"), max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)
    verified = models.BooleanField(default=False)
    has_onboarded = models.BooleanField(default=False)
    company = models.BooleanField(null=True, blank=True, default=None)
    auth_provider = models.CharField(
        max_length=10, choices=AUTH_PROVIDERS, default="email"
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name"]

    objects = CustomUserManager()

    def __str__(self) -> str:
        return self.email


"""INDIVIDUAL USERS SKILLS MODEL"""


class UserSkills(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="user_skills", db_index=True
    )
    name = models.CharField(max_length=100, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class UserCategories(models.Model):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


"""INDIVIDUAL USERS PROFILE MODEL"""


class Profile(models.Model):
    class JobLocationChoices(models.TextChoices):
        REMOTE = "R", "Remote"
        ONSITE = "O", "Onsite"
        HYBRID = "H", "Hybrid"

    class JobEmploymentChoices(models.TextChoices):
        Full_Time = "F", "Full-Time"
        Part_Time = "P", "Part-Time"
        Contract = "C", "Contract"

    class ExperienceLevel(models.TextChoices):
        ENTRY = "Entry", "Entry-Level"
        MID = "Mid", "Mid-Level"
        SENIOR = "Senior", "Senior-Level"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    bio = models.TextField(null=True, blank=True)
    location = models.CharField(max_length=100, null=True, blank=True)
    job_location = models.CharField(
        max_length=2,
        choices=JobLocationChoices.choices,
        default=JobLocationChoices.REMOTE,
    )
    employment_type = models.CharField(
        max_length=2,
        choices=JobEmploymentChoices.choices,
        default=JobEmploymentChoices.Full_Time,
    )
    max_salary = models.IntegerField(default=10)
    min_salary = models.IntegerField(default=10)
    currency = models.CharField(max_length=20, default="USD")
    phonenumbers = models.CharField(max_length=255, blank=True, null=True)
    github = models.CharField(max_length=100, null=True, blank=True)
    portfolio = models.CharField(max_length=100, null=True, blank=True)
    linkedin = models.CharField(max_length=100, null=True, blank=True)
    twitter = models.CharField(max_length=100, null=True, blank=True)
    skills = models.ManyToManyField(UserSkills)
    categories = models.ManyToManyField(UserCategories)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notifications = models.JSONField(default=None, null=True, blank=True)
    experience_level = models.CharField(
        max_length=10, choices=ExperienceLevel.choices, default=ExperienceLevel.ENTRY
    )
    years_of_experience = models.IntegerField(default=1)
    resume = CloudinaryField("resume", resource_type="raw", null=True, blank=True)
    cover_letter = CloudinaryField(
        "cover_letter", resource_type="raw", null=True, blank=True
    )
    image = CloudinaryField("image", null=True, blank=True)

    def __str__(self):
        return self.user.first_name


"""COMPANY PROFILE MODEL"""


class CompanyProfile(models.Model):
    owner = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="company_profile"
    )
    address = models.TextField(blank=True, null=True)
    website = models.URLField(max_length=200, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    phone_number = models.CharField(max_length=24, blank=True, null=True)
    company_name = models.CharField(max_length=60, blank=True, null=True)
    image = CloudinaryField("image", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return (
            self.owner.first_name
        )  # This will be taken as the company's name.                                         # If business is True


"""EMAIL VERIFICATION MODEL"""


# This is to store every email verification key issued
class EmailVerication_Keys(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="keys")
    key = models.CharField(max_length=100)
    exp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


"""PASSWORD RESET KEYS MDOEL"""


# This is to store every password reset token issued
class PasswordReset_keys(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pwd_keys")
    key = models.CharField(max_length=100)
    exp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


""" JOB SKILLS """


class JobSkills(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


""" JOBS MODEL """


class Jobs(models.Model):
    class CurrencyChoices(models.TextChoices):
        usd = "USD", "United States Dollar"
        ngn = "NGN", "Nigerian Naira"
        eur = "EUR", "Euros"
        gbp = "GBP", "Great Britain Pounds"

    class EmploymentType(models.TextChoices):
        REMOTE = "R", "Remote"
        ONSITE = "O", "Onsite"
        HYBRID = "H", "Hybrid"

    class ExperienceLevel(models.TextChoices):
        ENTRY = "Entry", "Entry-Level"
        MID = "Mid", "Mid-Level"
        SENIOR = "Senior", "Senior-Level"

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="jobs")
    title = models.CharField(max_length=50)
    description = models.TextField()
    location = models.CharField(max_length=255)
    categories = models.TextField(null=True)
    skills = models.ManyToManyField(JobSkills)
    max_salary = models.IntegerField(default=5000)
    min_salary = models.IntegerField(default=0)
    currency_type = models.CharField(max_length=30, default="USD")

    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices)
    experience_level = models.CharField(
        max_length=10, choices=ExperienceLevel.choices, default=ExperienceLevel.ENTRY
    )
    years_of_experience = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


""" JOB APPLICANTS MODEL """


class Applicant(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="applications"
    )
    job = models.ForeignKey(Jobs, on_delete=models.CASCADE, related_name="applicants")
    match_score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


""" WAITLIST MODEL """


class WaitList(models.Model):
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


""" SUBSCRIPTION MODEL """


class Subscription(models.Model):
    class SubscriptionPlans(models.TextChoices):
        free = "FREE"
        plus = "PLUS"
        pro = "PRO"

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="subscription"
    )
    amount = models.IntegerField()
    plan = models.CharField(max_length=10, choices=SubscriptionPlans.choices)
    reference = models.CharField(max_length=100, unique=True)


""""AI BINARY TRAINIGNG MODEL"""


class RecommenderModel(models.Model):
    name = models.CharField(max_length=255)
    model_data = models.BinaryField()  # This will store the serialized model
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Message(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        User,
        related_name="sent_messages",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255)
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    unlocked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.user.email} - ₦{self.balance}"

    def deposit(self, amount, reference=None, source="manual"):
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Deposit amount must be positive.")
        with transaction.atomic():
            self.balance += amount
            self.save()
            WalletTransaction.objects.create(
                wallet=self,
                amount=amount,
                type="deposit",
                reference=reference or self._generate_reference(),
                status="success",
                source=source,
            )

    def deduct(self, amount, description=None):
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Deduction amount must be positive.")
        if self.balance >= amount:
            with transaction.atomic():
                self.balance -= amount
                self.save()
                WalletTransaction.objects.create(
                    wallet=self,
                    amount=amount,
                    type="spend",
                    reference=self._generate_reference(),
                    status="success",
                    description=description,
                    source="wallet",
                )
            return True
        return False

    def _generate_reference(self):
        return str(uuid.uuid4())


class WalletTransaction(models.Model):
    TRANSACTION_TYPES = (
        ("deposit", "Deposit"),
        ("spend", "Spend"),
        ("bonus", "Bonus"),
    )

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
    )

    wallet = models.ForeignKey(
        Wallet, on_delete=models.CASCADE, related_name="transactions"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, default="deposit")
    reference = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    source = models.CharField(max_length=50, default="wallet")
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.wallet.user.email} - ₦{self.amount} - {self.get_status_display()}"
        )


class JobTweet(models.Model):
    tweet_id = models.BigIntegerField(unique=True)
    user_id = models.CharField(max_length=255)
    text = models.TextField()
    created_at = models.DateTimeField()
    tweet_link = models.URLField()

    def __str__(self):
        return f"{self.user_id}: {self.text[:50]}..."
