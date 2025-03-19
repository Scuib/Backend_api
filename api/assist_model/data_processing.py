from api.views import company
from ..models import Profile
from django.shortcuts import get_object_or_404
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from ..models import User, Assists


class DataPreprocessor:
    def __init__(self):
        self.assist_postings = pd.DataFrame()
        self.user_profiles = pd.DataFrame()
        self.vectorizer = TfidfVectorizer()

    def load_data(self, assist_id):
        # Load assist data for a specific assist ID
        try:
            assist_instance = Assists.objects.get(id=assist_id)
            # assist_skills_list = list(AssitSkills.objects.filter(assist=assist_instance).values_list('name', flat=True))
            assist_data = [
                {
                    "id": assist_instance.id,
                    "title": assist_instance.title,
                    "description": assist_instance.description,
                    "skills": " ".join(
                        assist_instance.skills.values_list("name", flat=True)
                    ),
                    "employment_type": assist_instance.employment_type,
                    "currency_type": assist_instance.currency_type,
                }
            ]
        except Assists.DoesNotExist:
            assist_data = []

        # Load all user data
        users = User.objects.filter(company=False)

        user_data = []
        for user in users:
            print(f"User : {user.id}")
            # user_instance = User.objects.get(id=user.id)
            profile = get_object_or_404(Profile, user=user)
            print(profile)

            user_skills_list = list(profile.skills.values_list("name", flat=True))
            user_categories_list = list(
                profile.categories.values_list("name", flat=True)
            )

            if profile:
                user_data.append(
                    {
                        "id": user.id,
                        "skills": " ".join(user_skills_list),
                        "category": " ".join(user_categories_list),
                    }
                )

        self.assist_postings = pd.DataFrame(assist_data)
        self.user_profiles = pd.DataFrame(user_data)

        return self.assist_postings, self.user_profiles

    def preprocess_data(self):
        if not self.assist_postings.empty and "skills" in self.assist_postings.columns:
            self.assist_tfidf_matrix = self.vectorizer.fit_transform(
                self.assist_postings["skills"]
            )
        else:
            self.assist_tfidf_matrix = None

        if not self.user_profiles.empty and "skills" in self.user_profiles.columns:
            self.user_tfidf_matrix = self.vectorizer.fit_transform(
                self.user_profiles["skills"]
            )
        else:
            self.user_tfidf_matrix = None

    def get_feature_matrices(self):
        return self.user_tfidf_matrix, self.assist_tfidf_matrix
