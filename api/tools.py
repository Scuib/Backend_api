from random import randint
from .models import EmailVerication_Keys, User, PasswordReset_keys
from django.shortcuts import get_object_or_404
from datetime import datetime, timedelta
from django.utils import timezone


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

    expriation = datetime.now() + timedelta(hours=24)
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

    expriation = timezone.now() + timedelta(hours=1)
    PasswordReset_keys.objects.create(
        user = user,
        key = unique_key,
        exp = expriation
    )
    return unique_key, user.id # type: ignore Pylance warning
