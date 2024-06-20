from unicodedata import category
from django.db.models.signals import post_save
from .models import User, Profile, UserSkills, UserCategories, Image, CompanyProfile
from django.dispatch import receiver
import cloudinary.uploader
from scuibai.settings import BASE_DIR


@receiver(post_save, sender=User)
def create_user_signals(sender, instance, created, **kwargs):
    if created:
        if instance.company:  # Check if the user is a company
            return ""
        
        # Create UserSkills
        skill = UserSkills.objects.create(user_id=instance.id, name='english')
        skills = UserSkills.objects.filter(user_id=instance.id).values_list('name', flat=True)
        
        # Create UserCategories
        category = UserCategories.objects.create(user=instance.id, name='default')
        categories = UserCategories.objects.filter(user_id=instance.id).values_list('name', flat=True)
        
        # Create Profile
        profile = Profile.objects.create(user=instance, skills=skills, categories=categories)

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
            
            return instance.name

    return ""

