import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from ..models import Jobs, JobSkills, User, UserCategories, UserSkills, Profile
from ..serializer import JobSerializer, ProfileSerializer, UserSerializer

class DataPreprocessor:
    def __init__(self):
        self.job_postings = None
        self.user_profiles = None
        self.vectorizer = TfidfVectorizer()

    def load_data(self, job_id):
        # Query only the specific job using job_id
        job = Jobs.objects.get(id=job_id)
        job_skills_list = list(JobSkills.objects.filter(job=job).values_list('name', flat=True))
        
        job_data = [{
            'id': job.id,
            'description': job.description,
            'skills': ' '.join(job_skills_list),
            'category': job.categories
        }]
        
        users = User.objects.all().values()
        user_skills = UserSkills.objects.all().values()
        categories = UserCategories.objects.all().values()
        
        user_data = []
        for user in users:
            user_instance = User.objects.get(id=user['id'])
            user_skills_list = list(UserSkills.objects.filter(user=user_instance).values_list('name', flat=True))
            user_categories_list = list(UserCategories.objects.filter(user=user_instance).values_list('name', flat=True))
            user_data.append({
                'id': user['id'],
                'skills': ' '.join(user_skills_list),
                'category': ' '.join(user_categories_list)
            })
        
        self.job_postings = pd.DataFrame(job_data)
        self.user_profiles = pd.DataFrame(user_data)

        return self.job_postings, self.user_profiles

    def preprocess_data(self):
        if 'description' not in self.job_postings.columns or 'skills' not in self.user_profiles.columns:
            raise ValueError("Missing required columns in data files.")

        self.job_postings['description'] = self.job_postings['description'].fillna('')
        self.user_profiles['skills'] = self.user_profiles['skills'].fillna('')

        self.job_postings['combined'] = (self.job_postings['skills'] + ' ' + 
                                         self.job_postings['category'] + ' ' + 
                                         self.job_postings['description'])
        self.user_profiles['combined'] = (self.user_profiles['skills'] + ' ' + 
                                          self.user_profiles['category'])

        self.job_tfidf_matrix = self.vectorizer.fit_transform(self.job_postings['combined'])
        self.user_tfidf_matrix = self.vectorizer.transform(self.user_profiles['combined'])

    def get_feature_matrices(self):
        return self.user_tfidf_matrix, self.job_tfidf_matrix
