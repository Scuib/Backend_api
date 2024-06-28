import pandas as pd
import numpy as np
from scipy.sparse import vstack, hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import accuracy_score
import joblib
import os

# Importing the Django models
from ..models import User, Jobs, AllSkills, UserSkills, UserCategories, CompanyProfile, Profile, Resume, Cover_Letter, Image, EmailVerication_Keys, PasswordReset_keys, JobSkills, Applicants, Assits, AssitSkills

class JobAppMatching:
    def __init__(self, model_path='model.pkl', vectorizer_path='vectorizer.pkl'):
        self.model_path = model_path
        self.vectorizer_path = vectorizer_path
        self.vectorizer = None
        self.model = None
        self.label_encoder = None

    def load_data(self, job_id):
        try:
            job = Jobs.objects.get(id=job_id)
            applicants = User.objects.all()
            job_skills = [skill.name for skill in job.job_skills.all()]
            applicant_data = [{'id': applicant.id, 'skills': [skill.name for skill in applicant.skills.all()]} for applicant in applicants]

            job_df = pd.DataFrame([{
                'job_id': job.id,
                'title': job.title,
                'skills': " ".join(job_skills),
                'job_type': job.employment_type,
                'location': job.location,
                'budget': (job.min_salary + job.max_salary) / 2
            }])

            user_df = pd.DataFrame([{
                'applicant_id': data['id'],
                'skills': " ".join(data['skills']),
                'experience_level': Profile.objects.get(user__id=data['id']).experience_level,
                'job_type': Profile.objects.get(user__id=data['id']).job_location,
                'location': Profile.objects.get(user__id=data['id']).location,
                'rating': Profile.objects.get(user__id=data['id']).rating if hasattr(Profile.objects.get(user__id=data['id']), 'rating') else 0
            } for data in applicant_data])

            return job_df, user_df
        except Jobs.DoesNotExist:
            print(f"No job found with job ID {job_id}")
            return pd.DataFrame(), pd.DataFrame()

    def vectorize_skills(self, skills):
        if not self.vectorizer:
            self.vectorizer = TfidfVectorizer()
            skill_matrix = self.vectorizer.fit_transform(skills)
            joblib.dump(self.vectorizer, self.vectorizer_path)
        else:
            skill_matrix = self.vectorizer.transform(skills)
        return skill_matrix

    def prepare_data(self, job_df, user_df):
        job_skill_matrix = self.vectorize_skills(job_df['skills'])
        user_skill_matrix = self.vectorize_skills(user_df['skills'])

        self.label_encoder = LabelEncoder()
        job_label = self.label_encoder.fit_transform(job_df['title'])[0]

        features = hstack([user_skill_matrix, vstack([job_skill_matrix] * len(user_df))])
        labels = np.full(len(user_df), job_label)

        return features, labels

    def train_model(self, features, labels):
        X_train, X_test, y_train, y_test = train_test_split(features, labels, test_size=0.2, random_state=42)
        self.model = MLPClassifier(hidden_layer_sizes=(512, 256), activation='relu', max_iter=300)
        self.model.fit(X_train, y_train)
        joblib.dump(self.model, self.model_path)

        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        print(f"Model training completed with accuracy: {accuracy}")

    def load_model(self):
        if os.path.exists(self.model_path) and os.path.exists(self.vectorizer_path):
            self.model = joblib.load(self.model_path)
            self.vectorizer = joblib.load(self.vectorizer_path)
        else:
            print("Model or vectorizer not found. Please train the model first.")

    def recommend_applicants(self, job_id, experience_level, job_type, top_n=3):
        if not self.model:
            print("Model not loaded. Please load the model first.")
            return pd.DataFrame()

        job_df, user_df = self.load_data(job_id)

        if job_df.empty or user_df.empty:
            return pd.DataFrame()

        job_skills = vstack([self.vectorizer.transform([job_df.iloc[0]['skills']])] * len(user_df))

        filtered_applicants = user_df[(user_df['experience_level'] == experience_level) & (user_df['job_type'] == job_type)]
        if filtered_applicants.empty:
            print(f"No applicants found with experience level {experience_level} and job type {job_type}")
            return pd.DataFrame()

        filtered_applicant_skill_matrix = self.vectorizer.transform(filtered_applicants['skills'])
        features = hstack([filtered_applicant_skill_matrix, job_skills[:len(filtered_applicants)]])

        applicant_predictions = self.model.predict_proba(features)[:, 1]
        top_applicants = np.argsort(applicant_predictions)[::-1][:top_n]
        recommended_applicants = filtered_applicants.iloc[top_applicants][['applicant_id', 'skills', 'experience_level', 'job_type', 'location', 'rating']]

        return recommended_applicants

# Example usage:
# job_matcher = JobAppMatching()
# job_matcher.load_model()
# recommended = job_matcher.recommend_applicants(job_id=123, experience_level='Senior', job_type='R')
# print(recommended)
