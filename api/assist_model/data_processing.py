import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from ..models import User, Assits, AssitSkills, UserSkills, UserCategories

class DataPreprocessor:
    def __init__(self):
        self.job_postings = None
        self.user_profiles = None
        self.vectorizer = TfidfVectorizer()

    def load_data(self):
        # Load assist data
        assists = Assits.objects.all().values()
        # assist_skills = AssitSkills.objects.all().values()
        
        assist_data = []
        for assist in assists:
            assist_instance = Assits.objects.get(id=assist['id'])
            assist_skills_list = list(AssitSkills.objects.filter(assist=assist_instance).values_list('name', flat=True))
            assist_data.append({
                'id': assist['id'],
                'title': assist['title'],
                'description': assist['description'],
                'skills': ' '.join(assist_skills_list),
                'employment_type': assist['employment_type'],
                'currency_type': assist['currency_type']
            })
        
        # Load user data
        users = User.objects.all().values()
        # user_skills = UserSkills.objects.all().values()
        # categories = UserCategories.objects.all().values()
        
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
        
        self.assist_postings = pd.DataFrame(assist_data)
        self.user_profiles = pd.DataFrame(user_data)

        return self.assist_postings, self.user_profiles

    def preprocess_data(self):
        self.assist_tfidf_matrix = self.vectorizer.fit_transform(self.assist_postings['skills'])
        self.user_tfidf_matrix = self.vectorizer.fit_transform(self.user_profiles['skills'])

    def get_feature_matrices(self):
        return self.user_tfidf_matrix, self.assist_tfidf_matrix
