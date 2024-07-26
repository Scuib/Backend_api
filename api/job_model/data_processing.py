import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from django.shortcuts import get_object_or_404

from api.views import company

from ..models import Jobs, JobSkills, User, UserCategories, UserSkills, Profile
from ..serializer import JobSerializer, ProfileSerializer, UserSerializer


class DataPreprocessor:
    def __init__(self):
        self.job_posting = None
        self.user_profiles = None
        self.vectorizer = TfidfVectorizer()

    def load_data(self, job_id):
        # Query only the specific job using job_id
        job = Jobs.objects.get(id=job_id)
        job_data = [{
            'id': job.id,
            'description': job.description,
            'skills': ' '.join(list(job.skills.values_list('name', flat=True))),
            'category': ' '.join([cat for cat in [job.categories] if cat])
        }]
        print(f"List of Job Data \n {job_data}")

        users = User.objects.filter(company=False)

        user_data = []
        for user in users:
            profile = get_object_or_404(Profile, user=user)
            # profile = Profile.objects.get(user=user)
            if profile:
                 user_data.append({
                    'id': user.id,
                    'skills': ' '.join(profile.skills.values_list('name', flat=True)),
                    'category': ' '.join(profile.categories.values_list('name', flat=True))
                })
        
        self.job_posting = pd.DataFrame(job_data)
        self.user_profiles = pd.DataFrame(user_data)

        return self.job_posting, self.user_profiles

    def preprocess_data(self):
        print(f"Job Post Columns: {self.job_posting.columns}")
        print(f"User Profiles Columns: {self.user_profiles.columns}")

        if 'description' not in self.job_posting.columns or 'skills' not in self.user_profiles.columns:
            raise ValueError("Missing required columns in data files.")
        
        # Convert lists in 'skills' column to strings
        self.job_posting['skills'] = self.job_posting['skills'].apply(lambda x: ' '.join(x) if isinstance(x, list) else x)
        self.user_profiles['skills'] = self.user_profiles['skills'].apply(lambda x: ' '.join(x) if isinstance(x, list) else x)

        self.job_posting['description'] = self.job_posting['description'].fillna('')
        self.user_profiles['skills'] = self.user_profiles['skills'].fillna('')

        # Convert 'category' to string if it's a list
        self.job_posting['category'] = self.job_posting['category'].apply(lambda x: ' '.join(x) if isinstance(x, list) else x)
        self.user_profiles['category'] = self.user_profiles['category'].apply(lambda x: ' '.join(x) if isinstance(x, list) else x)

        # Concatenate the strings
        self.job_posting['combined'] = (self.job_posting['skills'] + ' ' + 
                                         self.job_posting['category'] + ' ' + 
                                         self.job_posting['description'])
        self.user_profiles['combined'] = (self.user_profiles['skills'] + ' ' + 
                                          self.user_profiles['category'])

        # Print the dataframe to check
        print(self.job_posting)
        print(self.user_profiles)

        self.job_tfidf_matrix = self.vectorizer.fit_transform(self.job_posting['combined'])
        self.user_tfidf_matrix = self.vectorizer.transform(self.user_profiles['combined'])

    def get_feature_matrices(self):
        return self.user_tfidf_matrix, self.job_tfidf_matrix

