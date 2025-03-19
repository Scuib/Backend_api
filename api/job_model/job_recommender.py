import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from ..models import Jobs, User, UserSkills, Profile

# Currency map for locations
currency_map = {
    "USA": "USD",
    "Europe": "EUR",
    "Nigeria": "NGN",
    "Kenya": "KES",
    "Ghana": "GHS",
    "South Africa": "ZAR",
    "Morocco": "MAD",
    "Senegal": "XOF",
    "China": "CNY",
    "India": "INR",
    "Japan": "JPY",
    "Indonesia": "IDR",
    "South Korea": "KRW",
    "Philippines": "PHP",
}


class JobAppMatching:
    def __init__(self):
        self.tfidf = TfidfVectorizer()

    def load_job_from_db(self, job_id):
        """Fetch job details from the database."""
        try:
            job = Jobs.objects.get(id=job_id)
            return {
                "job_id": job.id,
                "owner": job.owner,
                "title": job.title,
                "skills": ";".join(job.skills.values_list("name", flat=True)),
                "experience_level": job.experience_level.lower().strip(),
                "years_of_experience": job.years_of_experience,
                "location": job.location.lower().strip(),
                "min_salary": job.min_salary,
                "max_salary": job.max_salary,
                "currency_type": currency_map.get(job.location, "USD"),
                "employment_type": job.employment_type,
            }
        except Jobs.DoesNotExist:
            print("Job not found.")
            return None

    def load_users_from_db(self):
        """Fetch all candidates from the database."""
        users = (
            User.objects.filter(company=False)
            .select_related("profile")  # Fetch profiles in one query
            .prefetch_related("userskills_set")  # Fetch skills efficiently
        )

        user_data = []
        for user in users:
            profile = getattr(user, "profile", None)
            if not profile:
                continue  # Skip users without a profile

            skills = ";".join(user.userskills_set.values_list("name", flat=True))
            user_data.append(
                {
                    "user_id": user.id,
                    "user_name": f"{user.first_name} {user.last_name}",
                    "skills": skills,
                    "experience_level": profile.experience_level.lower().strip(),
                    "years_of_experience": profile.years_of_experience,
                    "location": (profile.location or "").lower().strip(),
                    "job_location": profile.job_location.lower().strip(),
                    "min_salary": profile.min_salary or 0,
                    "max_salary": profile.max_salary or 0,
                    "currency_type": currency_map.get(profile.location, "USD"),
                }
            )

        return pd.DataFrame(user_data)

    def enrich_jobs_with_currency(self, jobs):
        # Add a currency symbol column to the job data
        jobs["currency_symbol"] = jobs["location"].map(
            lambda loc: currency_map.get(loc, "$")
        )  # Default to USD if not mapped
        return jobs

    
    def recommend_jobs(self, user_profile, job_data):
        """
        Function to recommend jobs based on user profile by matching skills, experience, location, and salary.
        """
        # Process the user profile
        user_skills = user_profile.get("skills", "")
        user_experience = user_profile.get(
            "experience", "entry"
        )  # default to 'entry' if not provided
        user_location = user_profile.get("location", "")
        user_min_salary = user_profile.get("min_salary")# Extract and convert
        user_max_salary = int(user_profile.get("max_salary", [0])[0])
        user_min_salary = int(user_profile.get("min_salary", 0))
        user_max_salary = int(user_profile.get("max_salary", 0))

        # Handle missing data
        job_data = job_data.fillna(
            {"skills": "", "experience_level": "entry", "location": ""}
        )

        # Step 1: Calculate Skills Similarity using TF-IDF Vectorization
        tfidf = TfidfVectorizer()
        job_skills_matrix = tfidf.fit_transform(job_data["skills"].fillna(""))

        # Convert user skills to a TF-IDF vector
        user_skills_vector = tfidf.transform([", ".join(user_skills)])

        # Compute cosine similarity between user skills and job skills
        skills_similarity = cosine_similarity(
            user_skills_vector, job_skills_matrix
        ).flatten()
        

        # Step 2: Match Experience Level
        experience_map = {"entry": 1, "mid": 2, "senior": 3, "lead": 4}
        user_experience_level = experience_map.get(
            user_experience, 1
        )  # Default to 'entry'

        # Experience match: check if the job experience level matches the user's experience
        experience_match = (
            job_data["experience_level"].map(experience_map) == user_experience_level
        )

        # Step 3: Match Location
        location_match = job_data["location"].eq(user_location)
        # location_match = job_data["location"] == user_location

        # Step 4: Salary Match (simple range check)
        job_data["min_salary"] = pd.to_numeric(job_data["min_salary"], errors="coerce")
        job_data["max_salary"] = pd.to_numeric(job_data["max_salary"], errors="coerce")

        salary_match = (job_data["min_salary"] <= user_max_salary) & (
            job_data["max_salary"] >= user_min_salary
        )

        # Step 5: Calculate Final Scores (weighted sum of all factors)
        scores = (
            (0.4 * skills_similarity)
            + (0.3 * experience_match.astype(int))
            + (0.2 * location_match.astype(int))
            + (0.1 * salary_match.astype(int))
        )

        # Debugging: Print scores and indices
        print(f"Scores: {scores}")
        top_job_indices = np.argsort(scores)[-5:][::-1]  # Sort and pick top 5
        print(f"Top Job Indices: {top_job_indices}")

        recommendations = []
        for idx in top_job_indices:
            job = job_data.iloc[idx]
            recommendations.append(
                {
                    "job_title": job["title"],
                    "company": job["owner"],
                    "location": job["location"],
                    "experience_level": job["experience_level"],
                    "skills": job["skills"],
                    "min_salary": job["min_salary"],
                    "max_salary": job["max_salary"],
                    "score": scores[idx],
                }
            )

        if not recommendations:
            print("No job recommendations found.")

        return recommendations


    def recommend_users(self, job_profile, user_data):
        """
        Recommend users for a job profile based on skills, experience, location, and salary.
        """
        # Extract job profile details
        job_skills = job_profile['skills'].split(';')
        job_experience = job_profile['experience_level'].strip().lower()
        job_years_of_experience = job_profile['years_of_experience']
        job_location = job_profile['location'].strip().lower()
        job_min_salary = int(job_profile.get('min_salary', 0))
        job_max_salary = int(job_profile.get('max_salary', 0))
        job_currency = job_profile['currency_type']

        # Step 1: Skills Matching
        tfidf = TfidfVectorizer()
        user_skills_matrix = tfidf.fit_transform(user_data['skills'])
        job_skills_vector = tfidf.transform([', '.join(job_skills)])
        skills_similarity = cosine_similarity(job_skills_vector, user_skills_matrix).flatten()

        # Step 2: Experience Level and Years of Experience Match
        experience_map = {'entry': 1, 'mid': 2, 'senior': 3, 'lead': 4}
        user_data['experience_numeric'] = user_data['experience_level'].map(experience_map).fillna(0).astype(int)
        job_experience_numeric = experience_map.get(job_experience, 1)

        experience_match = (user_data['experience_numeric'] >= job_experience_numeric)
        years_experience_match = (user_data['years_of_experience'] >= job_years_of_experience)

        # Step 3: Location and Preferred Job Location Match
        location_match = (user_data['location'].str.lower() == job_location)

        # Step 4: Salary Match
        salary_match = (
            (user_data['min_salary'] <= job_max_salary) &
            (user_data['max_salary'] >= job_min_salary) &
            (user_data['currency_type'] == job_currency)
        )

        # Step 5: Scoring and Recommendations
        scores = (
            (0.5 * skills_similarity) +
            (0.2 * experience_match.astype(int)) +
            (0.1 * years_experience_match.astype(int)) +
            (0.15 * location_match.astype(int)) +
            (0.05 * salary_match.astype(int))
        )

        # Get top 5 users
        top_users = user_data.iloc[np.argsort(scores)[-5:][::-1]]

        # Format recommendations
        recommendations = []
        for idx, user in top_users.iterrows():
            recommendations.append({
                'user_name': user['user_name'],
                'user_id': user['user_id'],
                'skills': user['skills'],
                'user_location': user['location'],
                'salary_range': f"{user['min_salary']} - {user['max_salary']} {user['currency_type']}",
                'years_of_experience': user['years_of_experience'],
                'experience_level': user['experience_level'],
                'match_score': scores[idx]
            })

        return recommendations
