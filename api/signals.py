from unicodedata import category
from django.db.models.signals import post_save
from .models import Jobs, User, Profile, UserSkills, UserCategories, Image, CompanyProfile
from django.dispatch import receiver
import cloudinary.uploader
from scuibai.settings import BASE_DIR
from .model.model import JobAppMatching


@receiver(post_save, sender=User)
def create_user_signals(sender, instance, created, **kwargs):
    if created:
        if instance.company:  # Check if the user is a company
            return ""
        
        # Create UserSkills
        skill = UserSkills.objects.create(user=instance, name='english')
        
        # Create UserCategories
        category = UserCategories.objects.create(user=instance, name='default')
        
        # Create Profile
        profile = Profile.objects.create(user=instance)

        return "All Models created"
    return ""

@receiver(post_save, sender=User)
def create_user_image(sender, instance, created, **kwargs):
    if created and not instance.company:
        file_path = str(BASE_DIR / 'static/default.jpg')
        file = cloudinary.uploader.upload(file_path)['public_id']
        Image.objects.create(user=instance, file=file)


@receiver(post_save, sender=User)
def create_company_signals(sender, instance, created, **kwargs):
    if created:
        if instance.company is True:
            company_profile = CompanyProfile.objects.create(owner=instance)
            company_profile.save()
            
            return instance.first_name

    return ""


@receiver(post_save, sender=Jobs)
def create_applicants_signals(sender, instance, created, **kwargs):
    if created:
        job_matcher = JobAppMatching()
        job_matcher.load_model()
        recommended = job_matcher.recommend_applicants(job_id=instance.id,
                                                       max_experience=instance.max_experience,
                                                       min_experience=instance.min_experience,
                                                       job_type=instance.employment_type)
        print(recommended)
