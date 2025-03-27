from os import name
from unicodedata import category
from django.db import models
from django.contrib.auth.models import AbstractUser, PermissionsMixin
from django.urls import translate_url
from django.utils.translation import gettext_lazy as _


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
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
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
    max_salary = models.IntegerField(default=100)
    min_salary = models.IntegerField(default=10)
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
    resume = CloudinaryField("resume", null=True, blank=True)
    cover_letter = CloudinaryField("cover_letter", null=True, blank=True)
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
    established_date = models.DateField(blank=True, null=True)
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
    currency_type = models.CharField(
        max_length=30, choices=CurrencyChoices.choices, default=CurrencyChoices.ngn
    )
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices)
    experience_level = models.CharField(
        max_length=10, choices=ExperienceLevel.choices, default=ExperienceLevel.ENTRY
    )
    years_of_experience = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


""" JOB APPLICANTS MODEL """


class Applicants(models.Model):
    user = models.ManyToManyField(User, related_name="applications")
    job = models.ForeignKey(Jobs, on_delete=models.CASCADE, related_name="applicants")
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
