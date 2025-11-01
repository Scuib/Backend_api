import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from ..models import Jobs, User, UserSkills, Profile
import time

from django.db.models import F, Value
from django.db.models.functions import Lower
from django.contrib.postgres.aggregates import StringAgg

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
                "categories": ";".join(job.categories.values_list("name", flat=True)),
                "experience_level": job.experience_level.lower().strip(),
                "years_of_experience": job.years_of_experience,
                "location": job.location.lower().strip(),
                "min_salary": job.min_salary,
                "max_salary": job.max_salary,
                "currency_type": job.currency_type,
                "employment_type": job.employment_type,
            }
        except Jobs.DoesNotExist:
            print("Job not found.")
            return None

    def load_users_from_db(self, skills=None, categories=None, location=None):
        """
        Load user profiles with optional filters for skills, categories, or location.
        Returns a pandas DataFrame of user data.
        """

        # Base queryset
        users = (
            User.objects.filter(company=False)
            .select_related("profile")
            .prefetch_related("user_skills", "profile__categories")
        )

        # Apply filters dynamically
        if skills:
            users = users.filter(user_skills__name__in=skills)
        if categories:
            users = users.filter(profile__categories__name__in=categories)
        if location:
            users = users.filter(profile__location__iexact=location)

        # Remove duplicates if multiple relations overlap
        users = users.distinct()

        # Annotate and prepare data
        users = users.annotate(
            skills_agg=StringAgg("user_skills__name", delimiter=";", distinct=True),
            experience_level=Lower("profile__experience_level"),
            location=Lower("profile__location"),
            job_location=Lower("profile__job_location"),
            years_of_experience=F("profile__years_of_experience"),
            min_salary=F("profile__min_salary"),
            max_salary=F("profile__max_salary"),
            currency=F("profile__currency"),
            categories_agg=StringAgg(
                "profile__categories__name", delimiter=";", distinct=True
            ),
        ).values(
            "id",
            "first_name",
            "last_name",
            "skills_agg",
            "experience_level",
            "years_of_experience",
            "location",
            "job_location",
            "min_salary",
            "max_salary",
            "currency",
            "categories_agg",
        )

        # Convert to DataFrame
        user_data = [
            {
                "user_id": user["id"],
                "user_name": f"{user['first_name']} {user['last_name']}",
                "skills": user["skills_agg"] or "",
                "experience_level": user["experience_level"] or "",
                "years_of_experience": user["years_of_experience"] or 0,
                "location": user["location"] or "",
                "job_location": user["job_location"] or "",
                "min_salary": user["min_salary"] or 0,
                "max_salary": user["max_salary"] or 0,
                "currency_type": user["currency"] or "",
                "categories": user["categories_agg"] or "",
            }
            for user in users
        ]

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
        user_min_salary = user_profile.get("min_salary")  # Extract and convert
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
        job_skills = job_profile["skills"].split(";")
        job_experience = job_profile["experience_level"].strip().lower()
        job_years_of_experience = job_profile["years_of_experience"]
        job_location = job_profile["location"].strip().lower()
        job_min_salary = int(job_profile.get("min_salary", 0))
        job_max_salary = int(job_profile.get("max_salary", 0))
        job_currency = job_profile["currency_type"]

        # Filter users who have at least one matching skill

        def has_matching_skill(user_skills_str):
            user_skills = [
                s.strip().lower() for s in user_skills_str.split(";") if s.strip()
            ]
            return any(skill in user_skills for skill in job_skills)

        user_data = user_data[user_data["skills"].apply(has_matching_skill)]

        # If no users have matching skills, return empty list early
        if user_data.empty:
            return []

        # Step 1: Skills Matching
        tfidf = TfidfVectorizer()
        user_skills_matrix = tfidf.fit_transform(user_data["skills"])
        job_skills_vector = tfidf.transform([", ".join(job_skills)])
        skills_similarity = cosine_similarity(
            job_skills_vector, user_skills_matrix
        ).flatten()

        # Step 2: Experience Level and Years of Experience Match
        experience_map = {"entry": 1, "mid": 2, "senior": 3, "lead": 4}
        user_data["experience_numeric"] = (
            user_data["experience_level"].map(experience_map).fillna(0).astype(int)
        )
        job_experience_numeric = experience_map.get(job_experience, 1)

        experience_match = user_data["experience_numeric"] >= job_experience_numeric
        years_experience_match = (
            user_data["years_of_experience"] >= job_years_of_experience
        )

        # Step 3: Location and Preferred Job Location Match
        location_match = user_data["location"].str.lower() == job_location

        # Step 4: Salary Match
        salary_match = (
            (user_data["min_salary"] <= job_max_salary)
            & (user_data["max_salary"] >= job_min_salary)
            & (user_data["currency_type"] == job_currency)
        )

        # Step 5: Scoring and Recommendations
        scores = (
            (0.5 * skills_similarity)
            + (0.2 * experience_match.astype(int))
            + (0.1 * years_experience_match.astype(int))
            + (0.15 * location_match.astype(int))
            + (0.05 * salary_match.astype(int))
        )

        user_data["match_score"] = scores
        filtered_users = user_data[user_data["match_score"] >= 0.4]

        # Sort users by match score in descending order
        sorted_users = filtered_users.sort_values(by="match_score", ascending=False)

        # Format recommendations
        recommendations = []
        for idx, user in sorted_users.iterrows():
            recommendations.append(
                {
                    "user_name": user["user_name"],
                    "user_id": user["user_id"],
                    "skills": user["skills"],
                    "user_location": user["location"],
                    "salary_range": f"{user['min_salary']} - {user['max_salary']} {user['currency_type']}",
                    "years_of_experience": user["years_of_experience"],
                    "experience_level": user["experience_level"],
                    "match_score": scores[idx],
                }
            )

        return recommendations

    def recommend_users_any_skills(self, skills, location, user_data):
        """
        Recommend users who have at least one of the specified skills and match the location exactly.

        Args:
            skills (List[str]): List of skills from frontend.
            location (str): Location from frontend.
            user_data (pd.DataFrame): DataFrame with 'skills', 'location', 'user_name', 'user_id'.

        Returns:
            List[dict]: List of matching users.
        """
        # Normalize input
        required_skills_set = set(skill.strip().lower() for skill in skills)
        location = location.strip().lower()

        def has_any_required_skills(user_skills_str):
            user_skills = set(
                skill.strip().lower() for skill in user_skills_str.split(";")
            )
            return bool(required_skills_set & user_skills)  # intersection not empty

        # Apply filters
        matches = user_data[
            user_data["skills"].apply(has_any_required_skills)
            & user_data["location"].str.contains(location, case=False, na=False)
        ]

        # Format output
        recommendations = []
        for _, user in matches.iterrows():
            recommendations.append(
                {
                    "user_name": user["user_name"],
                    "user_id": user["user_id"],
                    "skills": user["skills"],
                    "user_location": user["location"],
                }
            )

        return recommendations

    def recommend_users_any_categories(self, categories, location, user_data):
        """
        Recommend users who have at least one of the specified categories
        and match the location.

        Args:
            categories (List[str]): List of categories from frontend.
            location (str): Location from frontend.
            user_data (pd.DataFrame): DataFrame with 'categories', 'location', 'user_name', 'user_id'.

        Returns:
            List[dict]: List of matching users.
        """
        # Normalize input
        required_categories_set = set(cat.strip().lower() for cat in categories)
        location = location.strip().lower()

        def has_any_required_categories(user_categories):
            user_categories = set(
                cat.strip().lower() for cat in user_categories.split(";")
            )
            return bool(
                required_categories_set & user_categories
            )  # intersection not empty

        # Apply filters
        matches = user_data[
            user_data["categories"].apply(has_any_required_categories)
            & user_data["location"].str.contains(location, case=False, na=False)
        ]

        # Format output
        recommendations = []
        for _, user in matches.iterrows():
            recommendations.append(
                {
                    "user_name": user["user_name"],
                    "user_id": user["user_id"],
                    "categories": user["categories"],
                    "user_location": user["location"],
                }
            )

        return recommendations

    def recommend_users_categories(self, job_profile, user_data):
        """
        Recommend users for a job profile based on categories, experience, location, and salary.
        """
        # Extract job profile details
        job_categories = job_profile["categories"].split(";")
        job_experience = job_profile["experience_level"].strip().lower()
        job_years_of_experience = job_profile["years_of_experience"]
        job_location = job_profile["location"].strip().lower()
        job_min_salary = int(job_profile.get("min_salary", 0))
        job_max_salary = int(job_profile.get("max_salary", 0))
        job_currency = job_profile["currency_type"]

        # Step 1: Categories Matching (instead of Skills)
        tfidf = TfidfVectorizer()
        user_categories_matrix = tfidf.fit_transform(user_data["categories"])
        job_categories_vector = tfidf.transform([", ".join(job_categories)])
        categories_similarity = cosine_similarity(
            job_categories_vector, user_categories_matrix
        ).flatten()

        # Step 2: Experience Level and Years of Experience Match
        experience_map = {"entry": 1, "mid": 2, "senior": 3, "lead": 4}
        user_data["experience_numeric"] = (
            user_data["experience_level"].map(experience_map).fillna(0).astype(int)
        )
        job_experience_numeric = experience_map.get(job_experience, 1)

        experience_match = user_data["experience_numeric"] >= job_experience_numeric
        years_experience_match = (
            user_data["years_of_experience"] >= job_years_of_experience
        )

        # Step 3: Location and Preferred Job Location Match
        location_match = user_data["location"].str.lower() == job_location

        # Step 4: Salary Match
        salary_match = (
            (user_data["min_salary"] <= job_max_salary)
            & (user_data["max_salary"] >= job_min_salary)
            & (user_data["currency_type"] == job_currency)
        )

        # Step 5: Scoring and Recommendations
        scores = (
            (0.5 * categories_similarity)
            + (0.2 * experience_match.astype(int))
            + (0.1 * years_experience_match.astype(int))
            + (0.15 * location_match.astype(int))
            + (0.05 * salary_match.astype(int))
        )

        user_data["match_score"] = scores
        filtered_users = user_data[user_data["match_score"] >= 0.4]

        # Sort users by match score in descending order
        # sorted_users = filtered_users.sort_values(by="match_score", ascending=False)

        top_users = user_data.iloc[np.argsort(scores)[-5:][::-1]]
        # Format recommendations
        recommendations = []
        for idx, user in top_users.iterrows():
            recommendations.append(
                {
                    "user_name": user["user_name"],
                    "user_id": user["user_id"],
                    "categories": user["categories"],  # swapped in place of skills
                    "user_location": user["location"],
                    "salary_range": f"{user['min_salary']} - {user['max_salary']} {user['currency_type']}",
                    "years_of_experience": user["years_of_experience"],
                    "experience_level": user["experience_level"],
                    "match_score": scores[idx],
                }
            )

        return recommendations
