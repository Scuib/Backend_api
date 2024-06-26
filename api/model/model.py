import sqlite3
import pandas as pd
import numpy as np
from scipy.sparse import vstack, hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import accuracy_score

# # Connect to SQLite database
# conn = sqlite3.connect('/mnt/data/jobs_applicants.db')

# # Read specific columns from the jobs table
# jobs_df = pd.read_sql_query('SELECT job_id, title, skills, job_type, location, budget FROM jobs', conn)
# # Read user DataFrame from SQLite
# user_df = pd.read_sql_query('SELECT applicant_id, name, skills, experience_level, job_type, location, rating FROM applicants', conn)

# Get the data directly from user models
from api.models import (Jobs, User, UserSkills, UserCategories, CompanyProfile, Profile, Resume, Cover_Letter, Image, EmailVerication_Keys, PasswordReset_keys, Assits, AssitSkills)

# Read specific columns from the jobs table
jobs_qs = Jobs.objects.all().values('id', 'title', 'description', 'employment_type', 'location', 'max_salary', 'min_salary', 'experience_level')
jobs_df = pd.DataFrame.from_records(jobs_qs)

# Read user DataFrame from the applicants table
user_qs = User.objects.filter(company=False).values('id', 'first_name', 'last_name', 'profile__bio', 'profile__location', 'profile__job_location', 'profile__max_salary', 'profile__min_salary')
user_df = pd.DataFrame.from_records(user_qs)
# Merge the new columns into the applicants_df
# user_df = pd.merge(user_df, new_columns_df, on='applicant_id')

# Function to vectorize skills using TF-IDF
def vectorize_skills(skills):
    vectorizer = TfidfVectorizer()
    return vectorizer.fit_transform(skills)

# Vectorize job and user skills
job_skill_matrix = vectorize_skills(jobs_df['skills'])
user_skill_matrix = vectorize_skills(user_df['skills'])

# Encode job titles
job_labels = np.tile(jobs_df['title'].values, len(user_df))
le = LabelEncoder()
job_labels_encoded = le.fit_transform(job_labels)

# Ensure correct feature matrix construction
features = hstack([vstack([user_skill_matrix] * len(jobs_df)), vstack([job_skill_matrix] * len(user_df))])
labels = job_labels_encoded

# Train-test split
X_train, X_test, y_train, y_test = train_test_split(features, labels, test_size=0.2, random_state=42)

# Define the MLPClassifier model
model = MLPClassifier(hidden_layer_sizes=(512, 256), activation='relu', solver='adam', max_iter=50, random_state=42)

# Train the model
model.fit(X_train, y_train)

# Evaluate the model
y_pred = model.predict(X_test)
test_acc = accuracy_score(y_test, y_pred)
print(f'Test accuracy: {test_acc}')

# Function to get top applicants for a job
def top_applicants_for_job(job_title, experience_level, job_type, model, le, applicant_skill_matrix, job_skill_matrix, applicants, jobs, top_n=3):
    job_indices = jobs[(jobs['title'] == job_title) & (jobs['job_type'] == job_type)].index
    if job_indices.empty:
        print(f"No job found with title {job_title} and job type {job_type}")
        return pd.DataFrame()
    job_index = job_indices[0]
    job_skills = vstack([job_skill_matrix[job_index]] * len(applicants))
    features = hstack([applicant_skill_matrix, job_skills])
    
    # Filter applicants based on experience level and job type
    filtered_applicants = applicants[(applicants['experience_level'] == experience_level) & (applicants['job_type'] == job_type)]
    if filtered_applicants.empty:
        print(f"No applicants found with experience level {experience_level} and job type {job_type}")
        return pd.DataFrame()
    
    # Rebuild the feature matrix for filtered applicants
    filtered_applicant_skill_matrix = applicant_skill_matrix[filtered_applicants.index]
    features = hstack([filtered_applicant_skill_matrix, job_skills[:len(filtered_applicants)]])
    
    applicant_predictions = model.predict_proba(features)[:, 1]
    top_applicants = np.argsort(applicant_predictions)[::-1][:top_n]  # Get top n applicant indices
    recommended_applicants = filtered_applicants.iloc[top_applicants][['name', 'skills', 'experience_level', 'job_type', 'location', 'rating']]
    return recommended_applicants

# Example: Get top applicants for 'Data Scientist' job with 'Senior' experience level and 'Full-Time' job type
top_applicants = top_applicants_for_job('Data Scientist', 'Senior', 'Full-Time', model, le, user_skill_matrix, job_skill_matrix, user_df, jobs_df)
print("Top applicants for 'Data Scientist' (Senior level, Full-Time):")
for _, row in top_applicants.iterrows():
    print(f"{row['name']} (Skills: {row['skills']}, Experience Level: {row['experience_level']}, Job Type: {row['job_type']}, Location: {row['location']}, Rating: {row['rating']})")