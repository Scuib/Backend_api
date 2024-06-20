from unicodedata import category
from django.db.models.signals import post_save
from .models import User, Profile, UserSkills, UserCategories, Image, CompanyProfile
from django.dispatch import receiver
import cloudinary.uploader
from scuibai.settings import BASE_DIR


# Throw signal when user is created and saved
@receiver(post_save, sender=User)
# def create_user_signals(sender, instance, created, **kwargs):
#     if created:
#         if not instance.company is False:
#             return ""
#         # Create UserSkills
#         skill = UserSkills.objects.create(user_id=instance.id, name='english')

#         # Create UserCategories
#         category = UserCategories.objects.create(user_id=instance.id, name='defualt')

#         # Create Profile
#         profile = Profile.objects.create(
#             user=instance,
#             skills = skill,
#             category = category
#         )

#         # Create Image Field
#         # Save Defualt Pictures
#         file = cloudinary.uploader.upload(BASE_DIR / 'static/default.jpg')['public_id']
#         image = Image.objects.create(user=instance, file=file)

#         return "All Models created"

#     return ""


@receiver(post_save, sender=User)
def create_user_skills(sender, instance, created, **kwargs):
    if created and not instance.company:
        UserSkills.objects.create(user=instance, name='english')

@receiver(post_save, sender=User)
def create_user_categories(sender, instance, created, **kwargs):
    if created and not instance.company:
        UserCategories.objects.create(user=instance, name='default')

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created and not instance.company:
        Profile.objects.create(user=instance)

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

