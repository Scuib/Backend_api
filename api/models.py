from xml.etree.ElementInclude import default_loader
from django.db import models
from django.contrib.auth.models import AbstractUser, PermissionsMixin
from django.utils.translation import gettext_lazy as _
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

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name']

    objects = CustomUserManager()

    def create_profile(self):
        Profile.objects.create(user=self)

    def __str__(self) -> str:
        return self.email

class AllSkills(models.Model):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class UserSkills(models.Model):
    user_id = models.IntegerField()
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class Profile(models.Model):
    class JobLocationChoices(models.TextChoices):
        REMOTE = 'R', 'Remote'
        ONSITE = 'O', 'Onsite'
        BOTH = 'RO', 'Both'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(null=True, blank=True)
    skills = models.ForeignKey(UserSkills, on_delete=models.CASCADE, related_name='skills')
    location = models.CharField(max_length=100, null=True, blank=True)
    job_location = models.CharField(max_length=2, choices=JobLocationChoices.choices, default=JobLocationChoices.BOTH)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.first_name

class Resume(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='resume')
    file = CloudinaryField('resume')

class Cover_Letter(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cover_letter')
    file = CloudinaryField('cover_letter')

class Image(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='image')
    file = CloudinaryField('image')



# This is to store every email verification key issued 
class EmailVerication_Keys(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='keys')
    key = models.CharField(max_length=100)
    exp = models.DateTimeField()


# This is to store every password reset token issued
class PasswordReset_keys(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pwd_keys')
    key = models.CharField(max_length=100)
    exp = models.DateTimeField()



class Jobs(models.Model):
    class CurrencyChoices(models.TextChoices):
        usd = 'USD', 'United States Dollar'
        ngn = 'NGN', 'Nigerian Naira'
        eur = 'EUR', 'Euros'

    
    class EmploymentType(models.TextChoices):
        REMOTE = 'R', 'Remote'
        ONSITE = 'O', 'Onsite'

    class ExperienceLevel(models.TextChoices):
        entry = 'ENTRY', 'Entry Level'
        mid = 'MID', 'Mid Level'
        senior = 'SENIOR', 'Senior Level'
        lead = 'LEAD', 'Lead Level'
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='jobs')
    title = models.CharField(max_length=50)
    description = models.TextField()
    location = models.CharField(max_length=255)
    salary = models.IntegerField()
    currency_type = models.CharField(max_length=30, choices=CurrencyChoices.choices, default=CurrencyChoices.ngn)
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices)
    experience_level = models.CharField(max_length=20, choices=ExperienceLevel.choices)


class Applicants(models.Model):
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='applicant')
    job = models.ForeignKey(Jobs, on_delete=models.CASCADE, related_name='job')


class JobSkills(models.Model):
    job = models.ForeignKey(Jobs, on_delete=models.CASCADE, related_name='job_skills')
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name
