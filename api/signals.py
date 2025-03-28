# from django.shortcuts import get_object_or_404, get_list_or_404
from django.db.models.signals import post_save, post_delete
from django.shortcuts import get_object_or_404

from .models import (
    JobSkills,
    Jobs,
    User,
    Profile,
    UserSkills,
    UserCategories,
    CompanyProfile,
)
from django.dispatch import receiver
import cloudinary.uploader
from scuibai.settings import BASE_DIR
from api.job_model.data_processing import DataPreprocessor
from api.job_model.job_recommender import JobAppMatching

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


# Call when a new Job is created
# Sort out job applicants


# @receiver(job_created)
# def create_applicants_signals(sender, instance, **kwargs):
#     # Initialize and prepare the data
#     preprocessor = DataPreprocessor()
#     job_posting, user_profiles = preprocessor.load_data(instance.id)
#     preprocessor.preprocess_data()
#     preprocessor.match_experience()
#     preprocessor.match_category()
#     preprocessor.match_salary()

#     # Get qualified users
#     qualified = preprocessor.get_matching_scores()

#     # Initialize the Job Recommender and train it with the prepared data
#     recommender = JobAppMatching()
#     # recommender.train(preprocessor)

#     # Make recommendations based on the preprocessed data
#     # recommended_users = recommender.recommend_users(preprocessor)
#     recommended_users = recommender.recommend_users(job_id=instance.id)

#     # Extract the user IDs from the recommendations
#     recommended_user_ids = recommended_users["id"].tolist()

#     # Try to create or update the Applicants model with recommended users
#     try:
#         application = Applicants.objects.get(job=instance)
#         # Update existing applicants
#         application.user.set(User.objects.filter(id__in=recommended_user_ids))
#     except Applicants.DoesNotExist:
#         # Create a new applicants entry
#         application = Applicants.objects.create(job=instance)
#         application.user.set(User.objects.filter(id__in=recommended_user_ids))
