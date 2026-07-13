import logging
import pandas as pd
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import IngestedJob, MatchResult, Profile
from .job_model.job_recommender import JobAppMatching

logger = logging.getLogger(__name__)

EXPERIENCE_MAP = {
    "entry": "Entry",
    "mid": "Mid",
    "senior": "Senior",
    "lead": "Senior",
}

EMPLOYMENT_TYPE_MAP = {
    "full-time": "R",
    "part-time": "P",
    "contract": "C",
    "internship": "R",
    "freelance": "C",
    "temporary": "C",
}


def _infer_experience_level(years):
    if years is None:
        return "entry"
    if years >= 5:
        return "senior"
    elif years >= 2:
        return "mid"
    return "entry"


def _ingested_jobs_to_dataframe(jobs):
    rows = []
    for j in jobs:
        skills = ";".join((j.required_skills or []) + (j.preferred_skills or []))
        rows.append({
            "title": j.title,
            "owner": j.company or "",
            "location": (j.location or "").lower(),
            "experience_level": _infer_experience_level(j.years_experience),
            "skills": skills,
            "min_salary": j.salary_min or 0,
            "max_salary": j.salary_max or 0,
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


@api_view(["POST"])
@permission_classes([AllowAny])
def ingest_job_and_match(request):
    payload = request.data

    source_job_id = payload.get("job_id") or payload.get("id") or ""
    if not source_job_id:
        return Response(
            {"error": "job_id is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    existing = IngestedJob.objects.filter(source_job_id=source_job_id).first()
    if existing:
        return Response(
            {
                "detail": "Job already ingested",
                "ingested_job_id": existing.id,
                "match_count": existing.matches.count(),
            },
            status=status.HTTP_200_OK,
        )

    ingested = IngestedJob.objects.create(
        source_job_id=source_job_id,
        title=payload.get("job_title", "Untitled"),
        company=payload.get("company"),
        location=payload.get("location"),
        remote=payload.get("remote", False),
        salary_min=payload.get("salary_min"),
        salary_max=payload.get("salary_max"),
        salary_currency=payload.get("salary_currency", "USD"),
        required_skills=payload.get("required_skills", []),
        preferred_skills=payload.get("preferred_skills", []),
        years_experience=payload.get("years_experience"),
        employment_type=payload.get("employment_type"),
        description=payload.get("description"),
        source=payload.get("source", "scuib_jobs_ai"),
        raw_payload=payload,
    )

    skills_list = payload.get("required_skills", []) + payload.get("preferred_skills", [])
    skills_str = ";".join(skills_list) if skills_list else ""

    years = ingested.years_experience or 0
    exp_level = _infer_experience_level(years)

    job_profile = {
        "skills": skills_str,
        "experience_level": exp_level,
        "years_of_experience": years,
        "location": (ingested.location or "").lower(),
        "min_salary": ingested.salary_min or 0,
        "max_salary": ingested.salary_max or 0,
        "currency_type": ingested.salary_currency,
    }

    matcher = JobAppMatching()
    user_profiles = matcher.load_users_from_db()

    matched_users = []
    if not user_profiles.empty:
        try:
            matched_users = matcher.recommend_users(job_profile, user_profiles)
        except Exception as e:
            logger.error(f"Matching failed for job {ingested.id}: {e}")

    match_objects = []
    for user_data in matched_users:
        match = MatchResult(
            ingested_job=ingested,
            user_id=user_data["user_id"],
            user_name=user_data["user_name"],
            match_score=user_data["match_score"],
            skills=user_data.get("skills", ""),
            location=user_data.get("user_location", ""),
            years_of_experience=user_data.get("years_of_experience"),
            experience_level=user_data.get("experience_level"),
            salary_range=user_data.get("salary_range"),
        )
        match_objects.append(match)

    if match_objects:
        MatchResult.objects.bulk_create(match_objects)

    ingested.status = "matched"
    ingested.save(update_fields=["status"])

    return Response(
        {
            "detail": "Job ingested and matched",
            "ingested_job_id": ingested.id,
            "match_count": len(matched_users),
            "matches": [
                {
                    "user_id": m.user_id,
                    "user_name": m.user_name,
                    "match_score": m.match_score,
                    "skills": m.skills,
                    "location": m.location,
                }
                for m in match_objects
            ],
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def list_ingested_jobs(request):
    status_filter = request.query_params.get("status")
    limit = int(request.query_params.get("limit", 50))

    qs = IngestedJob.objects.all()
    if status_filter:
        qs = qs.filter(status=status_filter)

    jobs = qs[:limit]
    return Response(
        {
            "count": len(jobs),
            "results": [
                {
                    "id": j.id,
                    "source_job_id": j.source_job_id,
                    "title": j.title,
                    "company": j.company,
                    "location": j.location,
                    "remote": j.remote,
                    "salary_min": j.salary_min,
                    "salary_max": j.salary_max,
                    "salary_currency": j.salary_currency,
                    "required_skills": j.required_skills,
                    "preferred_skills": j.preferred_skills,
                    "years_experience": j.years_experience,
                    "employment_type": j.employment_type,
                    "description": j.description,
                    "source": j.source,
                    "status": j.status,
                    "match_count": j.matches.count(),
                    "created_at": j.created_at.isoformat(),
                }
                for j in jobs
            ],
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def get_ingested_job_matches(request, job_id):
    try:
        job = IngestedJob.objects.get(id=job_id)
    except IngestedJob.DoesNotExist:
        return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)

    matches = job.matches.all()
    return Response(
        {
            "job_id": job.id,
            "title": job.title,
            "status": job.status,
            "matches": [
                {
                    "user_id": m.user_id,
                    "user_name": m.user_name,
                    "user_email": m.user_email,
                    "match_score": m.match_score,
                    "skills": m.skills,
                    "location": m.location,
                    "years_of_experience": m.years_of_experience,
                    "experience_level": m.experience_level,
                    "salary_range": m.salary_range,
                }
                for m in matches
            ],
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def recommend_jobs_for_user(request):
    """
    Recommends ingested jobs to the authenticated user.
    Uses recommend_jobs() — matches user's profile against all ingested jobs.
    """
    user = request.user
    skills_list = list(user.user_skills.values_list("name", flat=True))

    try:
        profile = user.profile
    except Profile.DoesNotExist:
        return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)

    user_profile = {
        "skills": skills_list,
        "experience": (profile.experience_level or "entry").lower(),
        "location": (profile.location or "").lower(),
        "min_salary": profile.min_salary or 0,
        "max_salary": [profile.max_salary or 0],
    }

    jobs_qs = IngestedJob.objects.filter(status="matched")
    job_df = _ingested_jobs_to_dataframe(jobs_qs)
    if job_df.empty:
        return Response({"recommended_jobs": []})

    matcher = JobAppMatching()
    recommendations = matcher.recommend_jobs(user_profile, job_df)

    return Response({"recommended_jobs": recommendations})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_matched_jobs(request):
    """Returns all ingested jobs that were matched to the authenticated user."""
    user = request.user
    matches = MatchResult.objects.filter(user_id=user.id).select_related("ingested_job")

    results = []
    for m in matches:
        job = m.ingested_job
        results.append({
            "match_id": m.id,
            "match_score": m.match_score,
            "job": {
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "remote": job.remote,
                "salary_min": job.salary_min,
                "salary_max": job.salary_max,
                "salary_currency": job.salary_currency,
                "required_skills": job.required_skills,
                "preferred_skills": job.preferred_skills,
                "years_experience": job.years_experience,
                "employment_type": job.employment_type,
            },
            "matched_at": m.created_at.isoformat() if hasattr(m, "created_at") else None,
        })

    return Response({"matches": results})
