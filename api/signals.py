# from django.shortcuts import get_object_or_404, get_list_or_404
from django.db.models.signals import post_save, post_delete
from django.shortcuts import get_object_or_404

from .models import AssistApplicants, Assits, JobSkills, Jobs, User, Profile, UserSkills, UserCategories, Image, CompanyProfile, Applicants
from django.dispatch import receiver
import cloudinary.uploader
from scuibai.settings import BASE_DIR
from .job_model.data_processing import DataPreprocessor
from .job_model.job_recommender import JobRecommender
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

        # # Create UserSkills
        
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

    # Load and preprocess data
    data = DataPreprocessor()
    job_postings, user_profiles = data.load_data(job_id=instance.id)

    data.preprocess_data()
    user_tfidf_matrix, job_tfidf_matrix = data.get_feature_matrices()

    # Get positive pairs from application history
    positive_pairs = list(Applicants.objects.filter(job=instance).values_list('user__id', 'job_id'))

    # Train the recommender model
    recommender = JobRecommender()
    recommender.train(user_features=user_tfidf_matrix, job_features=job_tfidf_matrix, positive_pairs=positive_pairs)
    recommender.save_model('job_recommender_model.pkl')

    # Recommend users for the job
    recommended_user_indices = recommender.recommend(user_tfidf_matrix, job_tfidf_matrix, top_k=5)
    recommended_users = data.user_profiles.iloc[recommended_user_indices]['id'].tolist()
    print(recommended_users)

    if recommended_users:
        try:
            application = Applicants.objects.get(job=instance)
            # Update existing applicants
            application.user.set(User.objects.filter(id__in=recommended_users))
            application.save()
        except Applicants.DoesNotExist:
            # Create new applicants entry
            application = Applicants.objects.create(job=instance)
            application.user.set(User.objects.filter(id__in=recommended_users))


# @receiver(assist_created)
# def create_assist_applicants_signals(sender, instance, **kwargs):
#     print("Compiler: Hey I made it here 👋😊")
#     # Load and preprocess data
#     data = AssistDataProcessor()
#     print(data)
#     assist_postings, user_profiles = data.load_data(assist_id=instance.id)
#     data.preprocess_data()
#     user_tfidf_matrix, assist_tfidf_matrix = data.get_feature_matrices()

#     # Get positive pairs from application history
#     positive_pairs = list(AssistApplicants.objects.filter(assist=instance).values_list('applicants__id', 'assist_id'))

#     # Train the recommender model
#     recommender = AssistRecommender()
#     print(f"Recommender {recommender}")

#     # user_features, assist_features, positive_pairs
#     recommender.train(user_features=user_tfidf_matrix, assist_features=assist_tfidf_matrix, positive_pairs=positive_pairs)
#     recommender.save_model('assist_recommender_model.pkl')

#     # Recommend users for the assist
#     assist_index = data.assist_postings.index[data.assist_postings['id'] == instance.id].tolist()[0]
#     recommended_user_indices = recommender.recommend(assist_tfidf_matrix[assist_index], user_tfidf_matrix, top_k=5)
#     recommended_users = data.user_profiles.iloc[recommended_user_indices]['id'].tolist()
#     print(recommended_users)

#     if recommended_users:
#         try:
#             application = AssistApplicants.objects.get(assist=instance)
#             # Update existing applicants
#             result = application.applicants.set(User.objects.filter(id__in=recommended_users))
#             application.save()
#             print("result")
#         except Applicants.DoesNotExist:
#             # Create new applicants entry
#             application = AssistApplicants.objects.create(assist=instance)
#             result = application.applicants.set(User.objects.filter(id__in=recommended_users))

#             print(f"result: {result}")
@receiver(assist_created)
def create_assist_applicants_signals(sender, instance, **kwargs):
    print("Compiler: Hey I made it here 👋😊")

    # Load and preprocess data
    data = AssistDataProcessor()
    print(data)
    assist_postings, user_profiles = data.load_data(assist_id=instance.id)
    data.preprocess_data()
    user_tfidf_matrix, assist_tfidf_matrix = data.get_feature_matrices()

    # Get positive pairs from application history
    positive_pairs = list(AssistApplicants.objects.filter(assist=instance).values_list('applicants__id', 'assist_id'))

    # Train the recommender model
    recommender = AssistRecommender()
    print(f"Recommender {recommender}")

    recommender.train(user_features=user_tfidf_matrix, assist_features=assist_tfidf_matrix, positive_pairs=positive_pairs)
    recommender.save_model('assist_recommender_model.pkl')

    # Recommend users for the assist
    assist_index = data.assist_postings.index[data.assist_postings['id'] == instance.id].tolist()[0]
    recommended_user_indices = recommender.recommend(assist_tfidf_matrix[assist_index], user_tfidf_matrix, top_k=5)
    recommended_users = data.user_profiles.iloc[recommended_user_indices]['id'].tolist()
    print(recommended_users)

    if recommended_users:
        try:
            application = AssistApplicants.objects.get(assist=instance)
            # Update existing applicants
            application.applicants.set(User.objects.filter(id__in=recommended_users))
            application.save()
        except AssistApplicants.DoesNotExist:
            # Create new applicants entry
            application = AssistApplicants.objects.create(assist=instance)
            application.applicants.set(User.objects.filter(id__in=recommended_users))    
            application.save()


    