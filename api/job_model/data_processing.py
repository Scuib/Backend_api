import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from django.shortcuts import get_object_or_404
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
            'category': ' '.join([cat for cat in [job.categories] if cat]),
            'min_salary': job.min_salary,
            'max_salary': job.max_salary,
            'min_experience': job.min_experience,
            'max_experience': job.max_experience,
        }]
        print(f"List of Job Data \n {job_data}")
        
        profiles = Profile.objects.all()
        
        
        user_data = []
        for profile in profiles:
            try:    
                user_data.append({
                    'id': profile.user.id,
                    'skills': ' '.join(profile.skills.values_list('name', flat=True)),
                    'category': ' '.join(profile.categories.values_list('name', flat=True)),
                    'min_salary': profile.min_salary,
                    'max_salary': profile.max_salary,
                    'experience': profile.experience,
                })

            except:
                print(f"No profile found for user {profile.user.id}")
        
        self.job_posting = pd.DataFrame(job_data)
        self.user_profiles = pd.DataFrame(user_data)
        
        return self.job_posting, self.user_profiles

    def preprocess_data(self):
        print(self.job_posting.columns)
        print(self.user_profiles.columns)
        # Verify DataFrames exist and have required columns
        if not hasattr(self, 'job_posting') or not hasattr(self, 'user_profiles'):
            raise ValueError("Data not loaded. Call load_data() first.")
            
        required_columns = {
            'job_posting': ['description', 'skills', 'category'],
            'user_profiles': ['skills', 'category']
        }
        
        for df_name, columns in required_columns.items():
            df = getattr(self, df_name)
            missing_cols = [col for col in columns if col not in df.columns]
            if missing_cols:
                raise ValueError(f"Missing required columns in {df_name}: {missing_cols}")

        # Process text columns
        text_columns = ['skills', 'category']
        
        # Process job posting
        for col in text_columns:
            self.job_posting[col] = self.job_posting[col].apply(
                lambda x: ' '.join(x) if isinstance(x, list) else str(x)
            ).fillna('')
            
        # Process user profiles
        for col in text_columns:
            self.user_profiles[col] = self.user_profiles[col].apply(
                lambda x: ' '.join(x) if isinstance(x, list) else str(x)
            ).fillna('')

        # Create combined features
        self.job_posting['combined'] = (
            self.job_posting['description'] + ' ' +
            self.job_posting['skills'] + ' ' +
            self.job_posting['category']
        ).str.lower()  # Convert to lowercase for better matching
        
        self.user_profiles['combined'] = (
            self.user_profiles['skills'] + ' ' +
            self.user_profiles['category']
        ).str.lower()  # Convert to lowercase for better matching
        
        # Debug information
        print("Job Posting Shape:", self.job_posting.shape)
        print("User Profiles Shape:", self.user_profiles.shape)
        
        # Create TF-IDF matrices
        try:
            self.job_tfidf_matrix = self.vectorizer.fit_transform(self.job_posting['combined'])
            self.user_tfidf_matrix = self.vectorizer.transform(self.user_profiles['combined'])
        except Exception as e:
            raise ValueError(f"Error creating TF-IDF matrices: {str(e)}")
        
    def get_feature_matrices(self):
        return self.user_tfidf_matrix, self.job_tfidf_matrix

    def match_experience(self):
        job_min_exp = self.job_posting['min_experience'].iloc[0]
        job_max_exp = self.job_posting['max_experience'].iloc[0]
        self.user_profiles['exp_match'] = self.user_profiles['experience'].apply(
            lambda x: job_min_exp <= x <= job_max_exp
        )

    def match_category(self):
        job_categories = set(self.job_posting['category'].iloc[0].split())
        self.user_profiles['category_match'] = self.user_profiles['category'].apply(
            lambda x: bool(set(x.split()) & job_categories)
        )

    def match_salary(self):
        job_min_salary = self.job_posting['min_salary'].iloc[0]
        job_max_salary = self.job_posting['max_salary'].iloc[0]
        self.user_profiles['salary_match'] = (
            (self.user_profiles['min_salary'] <= job_max_salary) &
            (self.user_profiles['max_salary'] >= job_min_salary)
        )

    def get_matching_scores(self, min_score=1):
        self.match_experience()
        self.match_category()
        self.match_salary()
        
        # Combine all matching criteria
        self.user_profiles['total_match'] = (
            self.user_profiles['exp_match'].astype(int) +
            self.user_profiles['category_match'].astype(int) +
            self.user_profiles['salary_match'].astype(int)
        )
        print(f"Total match: {self.user_profiles['total_match']}")
        
        # Filter users based on the minimum score
        qualified_users = self.user_profiles[self.user_profiles['total_match'] >= min_score]
        print(f"Qualified: {qualified_users}")
        
        # Sort by total_match score in descending order
        qualified_users = qualified_users.sort_values('total_match', ascending=False)
        
        return qualified_users[['id', 'total_match']]