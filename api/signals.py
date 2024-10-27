# from django.shortcuts import get_object_or_404, get_list_or_404
from django.db.models.signals import post_save, post_delete
from django.shortcuts import get_object_or_404

from .models import AssistApplicants, Assits, JobSkills, Jobs, User, Profile, UserSkills, UserCategories, Image, CompanyProfile, Applicants
from django.dispatch import receiver
import cloudinary.uploader
from scuibai.settings import BASE_DIR
from api.job_model.data_processing import DataPreprocessor
from api.job_model.job_recommender import JobRecommender
from .assist_model.data_processing import DataPreprocessor as AssistDataProcessor
from .assist_model.assist_recommender import AssistRecommender

from .custom_signal import job_created, assist_created


# Call when a user is created
# Create profile, userskills and usercategories

@receiver(post_save, sender=User)
def create_user_signals(sender, instance, created, **kwargs):
    if created:
        if instance.company:  # Check if the user is a company
            return ""

        # Create Profile
        profile = Profile.objects.create(user=instance)
        profile.save()

        return "All Models created"
    return ""

# Call when user Image is uploaded
# It creates a default picture

@receiver(post_save, sender=User)
def create_user_image(sender, instance, created, **kwargs):
    if created and not instance.company:
        file_path = str(BASE_DIR / 'static/default.jpg')
        file = cloudinary.uploader.upload(file_path)['public_id']
        Image.objects.create(user=instance, file=file)


# Call when a User with company==True is created
# Creates company porfile

@receiver(post_save, sender=User)
def create_company_signals(sender, instance, created, **kwargs):
    if created:
        if instance.company is True:
            company_profile = CompanyProfile.objects.create(owner=instance)
            company_profile.save()

            return instance.first_name

    return ""


# Call when a new Job is created
# Sort out job applicants


@receiver(job_created)
def create_applicants_signals(sender, instance, **kwargs):
    # Initialize and prepare the data
    preprocessor = DataPreprocessor()
    job_posting, user_profiles = preprocessor.load_data(instance.id)
    preprocessor.preprocess_data()
    preprocessor.match_experience()
    preprocessor.match_category()
    preprocessor.match_salary()
    
    # Get qualified users
    qualified = preprocessor.get_matching_scores()

    # Initialize the Job Recommender and train it with the prepared data
    recommender = JobRecommender()
    recommender.train(preprocessor)

    # Make recommendations based on the preprocessed data
    recommended_users = recommender.recommend(preprocessor)

    # Extract the user IDs from the recommendations
    recommended_user_ids = recommended_users['id'].tolist()

    # Try to create or update the Applicants model with recommended users
    try:
        application = Applicants.objects.get(job=instance)
        # Update existing applicants
        application.user.set(User.objects.filter(id__in=recommended_user_ids))
    except Applicants.DoesNotExist:
        # Create a new applicants entry
        application = Applicants.objects.create(job=instance)
        application.user.set(User.objects.filter(id__in=recommended_user_ids))


