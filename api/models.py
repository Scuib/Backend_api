from django.db import models
from django.contrib.auth.models import AbstractUser, PermissionsMixin
from django.urls import translate_url
from django.utils.translation import gettext_lazy as _
import phonenumbers
from .managers import CustomUserManager
from cloudinary.models import CloudinaryField

class User(AbstractUser):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=100, blank=True, null=True)
    first_name = models.CharField(_('First Name'), max_length=100)
    last_name = models.CharField(_('Last Name'), max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)
    verified = models.BooleanField(default=False)
    company = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name']

    objects = CustomUserManager()

    def __str__(self) -> str:
        return self.email


# Model for all skills.
# Example: python, SQL
class AllSkills(models.Model):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


# Model for user skills.
# Example: python, SQL
# This model should have a limit 10
class UserSkills(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='skills')
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


# Model for user categories.
# Example: Backend Developer, Software Engineer
# This model should have a limit 5
class UserCategories(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name



class CompanyProfile(models.Model):
    owner = models.OneToOneField(User, on_delete=models.CASCADE, related_name='company_profile')
    address = models.TextField(blank=True, null=True)
    website = models.URLField(max_length=200, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    established_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.owner.first_name # This will be taken as the company's name. 
                                        # If business is True


class Profile(models.Model):
    class JobLocationChoices(models.TextChoices):
        REMOTE = 'R', 'Remote'
        ONSITE = 'O', 'Onsite'
        HYBRID = 'H', 'Hybrid'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(null=True, blank=True)
    location = models.CharField(max_length=100, null=True, blank=True)
    job_location = models.CharField(max_length=2, choices=JobLocationChoices.choices, default=JobLocationChoices.HYBRID)
    max_salary = models.IntegerField(default=100)
    min_salary = models.IntegerField(default=10)
    experience = models.IntegerField(default=1)
    phonenumbers = models.CharField(max_length=255, blank=True, null=True)
    github = models.CharField(max_length=100, null=True, blank=True)
    linkedin = models.CharField(max_length=100, null=True, blank=True)
    twitter = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.first_name


class Resume(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='resume')
    file = CloudinaryField('resume')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Cover_Letter(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cover_letter')
    file = CloudinaryField('cover_letter')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Image(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='image')
    file = CloudinaryField('image')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


# This is to store every email verification key issued 
class EmailVerication_Keys(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='keys')
    key = models.CharField(max_length=100)
    exp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


# This is to store every password reset token issued
class PasswordReset_keys(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pwd_keys')
    key = models.CharField(max_length=100)
    exp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



class Jobs(models.Model):
    class CurrencyChoices(models.TextChoices):
        usd = 'USD', 'United States Dollar'
        ngn = 'NGN', 'Nigerian Naira'
        eur = 'EUR', 'Euros'

    class EmploymentType(models.TextChoices):
        REMOTE = 'R', 'Remote'
        ONSITE = 'O', 'Onsite'
        HYBRID = 'H', 'Hybrid'

    class ExperienceLevel(models.TextChoices):
        entry = 'ENTRY', 'Entry Level'
        mid = 'MID', 'Mid Level'
        senior = 'SENIOR', 'Senior Level'
        lead = 'LEAD', 'Lead Level'

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='jobs')
    title = models.CharField(max_length=50)
    description = models.TextField()
    location = models.CharField(max_length=255)
    categories = models.TextField(null=True)
    max_salary = models.IntegerField()
    min_salary = models.IntegerField()
    currency_type = models.CharField(max_length=30, choices=CurrencyChoices.choices, default=CurrencyChoices.ngn)
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices)
    experience_level = models.CharField(max_length=20, choices=ExperienceLevel.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



class JobSkills(models.Model):
    job = models.ForeignKey(Jobs, on_delete=models.CASCADE, related_name='job_skills')
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class Applicants(models.Model):
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='applicant')
    job = models.ForeignKey(Jobs, on_delete=models.CASCADE, related_name='job')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



class Assits(models.Model):
    class CurrencyChoices(models.TextChoices):
        usd = 'USD', 'United States Dollar'
        ngn = 'NGN', 'Nigerian Naira'
        eur = 'EUR', 'Euros'

    class EmploymentType(models.TextChoices):
        REMOTE = 'R', 'Remote'
        ONSITE = 'O', 'Onsite'
        HYBRID = 'H', 'Hybrid'


    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assists')
    title = models.CharField(max_length=50)
    description = models.TextField(null=True, blank=True)
    max_pay = models.IntegerField(default=100)
    min_pay = models.IntegerField(default=10)
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices)
    currency_type = models.CharField(max_length=30, choices=CurrencyChoices.choices, default=CurrencyChoices.ngn)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class AssitSkills(models.Model):
    assist = models.ForeignKey(Assits, on_delete=models.CASCADE, related_name='assist_skills')
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name
