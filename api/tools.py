from random import randint
from .models import EmailVerication_Keys, User, PasswordReset_keys, JobSkills
from django.shortcuts import get_object_or_404
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Count

import random
import string

def generate_random_string(length):
    characters = string.ascii_letters + string.digits
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string

# Get a verification Key
def VerifyEmail_key(user_id: int):
    # Query If user exists
    try:
        user = get_object_or_404(User, id=user_id)
    except User.DoesNotExist:
        return False

    unique_key = ""
    while True:
        unique_key = ""
        for _ in range(4):
            unique_key += str(randint(0, 9))
        if not EmailVerication_Keys.objects.filter(key=unique_key).exists():
            break

    expriation = timezone.now() + timezone.timedelta(days=1)
    print(f"Expiration Time: {expriation}")
    EmailVerication_Keys.objects.create(
        user = user,
        key = unique_key,
        exp = expriation
    )
    return unique_key, expriation

# Forget password or Reset password token/key
def ResetPassword_key(email: int):
    # Query If user exists
    try:
        user = get_object_or_404(User, email=email)
    except User.DoesNotExist:
        return False

    unique_key = ""
    while True:
        unique_key = generate_random_string(12)
        if not PasswordReset_keys.objects.filter(key=unique_key).exists():
            break

    expriation = timezone.now() + timezone.timedelta(hours=1)
    PasswordReset_keys.objects.create(
        user = user,
        key = unique_key,
        exp = expriation
    )
    return unique_key, user.id # type: ignore Pylance warning


def cleanup_duplicate_skills():
    # Find all skills with duplicate names
    duplicates = JobSkills.objects.values('name').annotate(
        count=Count('id')).filter(count__gt=1)
    
    for duplicate in duplicates:
        skills = JobSkills.objects.filter(name=duplicate['name']).order_by('id')
        # Keep the first one
        primary_skill = skills.first()
        # Get all other duplicates
        duplicate_skills = skills.exclude(id=primary_skill.id)
        
        # Update all jobs using duplicate skills to use the primary skill
        for skill in duplicate_skills:
            # Update all relationships to point to the primary skill
            skill.jobs_set.all().update(skills=primary_skill)
            # Delete the duplicate skill
            skill.delete()

    print("Cleanup complete!")
