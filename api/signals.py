
from django.db.models.signals import post_save, post_delete
from .models import JobSkills, Jobs, User, Profile, UserSkills, UserCategories, Image, CompanyProfile, Applicants
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
    print(f"Job {instance.id} - {instance.title} has been {'created' if created else 'updated'}.")
    
    job_matcher = JobAppMatching()
    job_matcher.load_model()
    
    recommended = job_matcher.recommend_applicants(
        job_id=instance.id,
        max_experience=instance.max_experience,
        min_experience=instance.min_experience,
        job_type=instance.employment_type
    )
    
    print(f"Recommended applicants for job {instance.id}: {recommended}")
    
    Applicants.objects.filter(job=instance).delete()
    print(f"Existing applicants for job {instance.id} deleted.")

    for x in recommended.itertuples():
        applicant = User.objects.get(id=x.applicant_id)
        Applicants.objects.create(applicant=applicant, job=instance)
        print(f"Applicant {applicant.id} assigned to job {instance.id}.")

@receiver(post_save, sender=JobSkills)
@receiver(post_delete, sender=JobSkills)
def update_applicants_on_skills_change(sender, instance, **kwargs):
    job = instance.job
    print(f"Skills for job {job.id} - {job.title} have been {'created/updated' if isinstance == JobSkills else 'deleted'}.")

    job_matcher = JobAppMatching()
    job_matcher.load_model()
    
    recommended = job_matcher.recommend_applicants(
        job_id=job.id,
        max_experience=job.max_experience,
        min_experience=job.min_experience,
        job_type=job.employment_type
    )
    
    print(f"Recommended applicants for job {job.id} after skills change: {recommended}")

    Applicants.objects.filter(job=job).delete()
    print(f"Existing applicants for job {job.id} deleted.")

    for x in recommended.itertuples():
        applicant = User.objects.get(id=x.applicant_id)
        Applicants.objects.create(applicant=applicant, job=job)
        print(f"Applicant {applicant.id} assigned to job {job.id}.")