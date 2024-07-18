# from django.shortcuts import get_object_or_404, get_list_or_404
from django.db.models.signals import post_save, post_delete

from api.views import assist
from .models import AssistApplicants, Assits, JobSkills, Jobs, User, Profile, UserSkills, UserCategories, Image, CompanyProfile, Applicants
from django.dispatch import receiver
import cloudinary.uploader
from scuibai.settings import BASE_DIR
from .job_model.data_processing import DataPreprocessor
from .job_model.job_recommender import JobRecommender
from .assist_model.data_processing import DataPreprocessor as AssistDataProcessor
from .assist_model.assist_recommender import AssistRecommender


# Call when a user is created
# Create profile, userskills and usercategories

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

@receiver(post_save, sender=Jobs)
def create_applicants_signals(sender, instance, created, **kwargs):

    # Load and preprocess data
    data = DataPreprocessor()
    job_postings, user_profiles = data.load_data(job_id=instance.id)

    if job_postings.empty:
        print(f"No Job postings found for id: {instance.id}")
        return
    data.preprocess_data()
    user_tfidf_matrix, job_tfidf_matrix = data.get_feature_matrices()

    # Get positive pairs from application history
    positive_pairs = list(Applicants.objects.filter(job=instance).values_list('applicants__id', 'job_id'))

    # Train the recommender model
    recommender = JobRecommender()
    recommender.train(user_features=user_tfidf_matrix, job_features=job_tfidf_matrix, positive_pairs=positive_pairs)
    recommender.save_model('job_recommender_model.pkl')

    # Recommend users for the job
    job_index = data.job_postings.index[data.job_postings['id'] == instance.id].tolist()[0]

    if job_index.empty:
        print(f"No Job Index found for id: {instance.id}")
        return

    recommended_user_indices = recommender.recommend(job_tfidf_matrix[job_index], user_tfidf_matrix, top_k=5)
    recommended_users = data.user_profiles.iloc[recommended_user_indices]['id'].tolist()
    print(recommended_users)

    if recommended_users:
        try:
            application = Applicants.objects.get(job=instance)
            # Update existing applicants
            application.applicants.set(User.objects.filter(id__in=recommended_users))
            application.save()
        except Applicants.DoesNotExist:
            # Create new applicants entry
            application = Applicants.objects.create(job=instance)
            application.applicants.set(User.objects.filter(id__in=recommended_users))
    
    # DEBUG
    # print(recommender.load_model('job_recommender_model.pkl'))
    # print("Job Posting Data: ", job_postings)
    # print("User Profiles Data: ", user_profiles)
    # print("User TF-IDF Matrix: ", user_tfidf_matrix)
    # print("Job TF-IDF Matrix: ", job_tfidf_matrix)


# Update the applicants if Job skills gets updated

@receiver(post_save, sender=JobSkills)
@receiver(post_delete, sender=JobSkills)
def update_applicants_on_skills_change(sender, instance, **kwargs):
    # Load and preprocess data
    data = DataPreprocessor()
    job_postings, user_profiles = data.load_data(job_id=instance.job.id)
    data.preprocess_data()
    user_tfidf_matrix, job_tfidf_matrix = data.get_feature_matrices()

    # Get positive pairs from application history
    positive_pairs = list(Applicants.objects.filter(job=instance.job).values_list('applicants__id', 'job_id'))

    # Train the recommender model
    recommender = JobRecommender()
    recommender.train(user_features=user_tfidf_matrix, job_features=job_tfidf_matrix, positive_pairs=positive_pairs)
    recommender.save_model('job_recommender_model.pkl')

    # Recommend users for the job
    job_index = data.job_postings.index[data.job_postings['id'] == instance.id].tolist()[0]
    recommended_user_indices = recommender.recommend(job_tfidf_matrix[job_index], user_tfidf_matrix, top_k=5)
    recommended_users = data.user_profiles.iloc[recommended_user_indices]['id'].tolist()
    print(recommended_users)

    if recommended_users:
        try:
            application = Applicants.objects.get(job=instance.job)
            # Update existing applicants
            application.applicants.set(User.objects.filter(id__in=recommended_users))
            application.save()
        except Applicants.DoesNotExist:
            # Create new applicants entry
            application = Applicants.objects.create(job=instance.job)
            application.applicants.set(User.objects.filter(id__in=recommended_users))


@receiver(post_save, sender=Assits)
def create_assist_applicants_signals(sender, instance, created, **kwargs):

    # Load and preprocess data
    data = AssistDataProcessor()
    job_postings, user_profiles = data.load_data(assist_id=instance.id)
    data.preprocess_data()
    user_tfidf_matrix, assist_tfidf_matrix = data.get_feature_matrices()

    # Get positive pairs from application history
    positive_pairs = list(AssistApplicants.objects.filter(assist=instance).values_list('applicants__id', 'assist_id'))

    # Train the recommender model
    recommender = AssistRecommender()
    # user_features, assist_features, positive_pairs
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
        except Applicants.DoesNotExist:
            # Create new applicants entry
            application = AssistApplicants.objects.create(assist=instance)
            application.applicants.set(User.objects.filter(id__in=recommended_users))


