import os
import requests
import cloudinary.uploader
from django.shortcuts import render, get_object_or_404
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from datetime import timedelta
from uuid import uuid4
import cloudinary
from django.core.mail import EmailMultiAlternatives
from django.core.files.uploadedfile import UploadedFile
import pandas as pd
import json
from django.views.decorators.csrf import csrf_exempt
import time

from .models import (
    BoostChatThread,
    BoostJobs,
    BoostSubscription,
    BoostUnlock,
    CompanyProfile,
    JobPreference,
    Profile,
    User,
    EmailVerication_Keys,
    Subscription,
    PasswordReset_keys,
    JobSkills,
    UserCategories,
    UserSkills,
    WaitList,
    JobSkills,
    Jobs,
    Applicant,
    Message,
    Wallet,
    WalletTransaction,
    JobTweet,
)

from .serializer import (
    BoostJobSerializer,
    CompanySerializer,
    DisplayProfileSerializer,
    JobPreferenceSerializer,
    MyTokenObtainPairSerializer,
    UserSerializer,
    ProfileSerializer,
    EmailVerifySerializer,
    ApplicantSerializer,
    LoginSerializer,
    JobSerializer,
    CompanySerializer,
    DisplayUsers,
    GoogleAuthSerializer,
    CompanyProfileSerializer,
    MessageSerializer,
    WalletTransactionSerializer,
    JobTweetSerializer,
    SentMessageSerializer,
)

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .tools import VerifyEmail_key, ResetPassword_key, cleanup_duplicate_skills
from django.contrib.auth.hashers import make_password, check_password
from django.template.loader import get_template
from allauth.account.models import EmailAddress
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from django.conf import settings
from .custom_signal import job_created, assist_created
from api.job_model.data_processing import DataPreprocessor
import resend
from scuibai.settings import RESEND_API_KEY
from django.core.mail import send_mail
import uuid
from decimal import Decimal

from django.utils import timezone
from api.job_model.job_recommender import JobAppMatching

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import snscrape.modules.twitter as sntwitter
from .utils import cleanup_messages, cleanup_old_jobs

# Activate the resend with the api key
resend.api_key = settings.NEW_RESEND_API_KEY
BOOST_MESSAGE_COST = 300  # Naira


def home(request):
    return render(request, "home.html")


def generate_reference():
    return str(uuid.uuid4())


UNLOCK_COST = 30.00  # Naira


# Get token or login View
class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer


""" AUTH """


# Register View
@swagger_auto_schema(
    method="post",
    operation_summary="Registers a new user",
    operation_description="Register new users, company or individuals by providing basic details such as email, first name, last name, and password",
    request_body=UserSerializer,
    responses={
        201: openapi.Response("User registered successfully"),
        400: "Bad request",
    },
)
@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    serialized_data = UserSerializer(data=request.data)

    if serialized_data.is_valid():
        user = serialized_data.save()
        EmailAddress.objects.create(user=user, email=user.email)  # type: ignore

        key, exp = VerifyEmail_key(user.id)

        template = get_template("register/verify_email.html")
        context = {"user": user, "otp": key, "expirary_date": exp}
        html = template.render(context)

        params: resend.Emails.SendParams = {
            "from": "Scuibai <godwin@scuib.com>",
            "to": [user.email],
            "subject": "VERIFY YOUR EMAIL",
            "html": html,
        }

        try:
            r = resend.Emails.send(params)
        except Exception as e:
            print(f"Error: {e}")
            user.delete()
            return Response(
                {
                    "message": "Registration Failed: Failed to send OTP. Please try again"
                },
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )
        return Response(
            {
                "message": "User Registered Successfully, Check email for otp code",
                "data": {
                    "key": key,
                    "exp": exp,
                    "is_Verified": user.verified,
                    "email": user.email,
                },
            },
        )

    return Response(serialized_data.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method="post",
    operation_summary="Resend Verify Email",
    operation_description="This endpoint resends email verification code to the user",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["email"],
        properties={
            "email": openapi.Schema(
                type=openapi.TYPE_STRING,
                format="email",
                description="User's email address",
            ),
        },
    ),
    responses={
        201: openapi.Response(
            description="Email verification sent",
            examples={
                "detail": {"name": "user.first_name", "key": "key", "expires": "exp"},
            },
        ),
        400: openapi.Response(
            description="Validation error",
            examples={
                "application/json": {
                    "email": ["This field is required."],
                }
            },
        ),
        401: openapi.Response(
            description="Invalid email",
            examples={"application/json": {"error": "Invalid email"}},
        ),
    },
)
@api_view(["POST"])
@permission_classes([AllowAny])
def resend_verify_email(request):
    """Verifies user email by validating token"""
    try:
        email = request.data["email"]
        unverified_email = EmailAddress.objects.get(email=email)
        user = unverified_email.user

        key, exp = VerifyEmail_key(user.id)

        return Response({"detail": {"name": user.first_name, "key": key, "expires": exp}}, status=status.HTTP_201_CREATED)  # type: ignore
    except:
        return Response("Email does not exist", status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method="post",
    operation_summary="Logout a user",
    operation_description="Logs out the authenticated user by blacklisting their refresh token.",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["refresh"],
        properties={
            "refresh": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="User's refresh token to be blacklisted",
            ),
        },
    ),
    responses={
        205: openapi.Response(
            description="LogOut Successful",
            examples={"application/json": {"detail": "LogOut Successful"}},
        ),
        400: openapi.Response(
            description="LogOut Unsuccessful",
            examples={
                "application/json": {"success": "fail", "detail": "LogOut UnSuccessful"}
            },
        ),
    },
)
@api_view(["GET", "POST", "PUT"])
@permission_classes([IsAuthenticated])
def logout(request):
    """Logs a user out of the platform"""
    try:
        refresh_token = request.data["refresh"]
        token = RefreshToken(refresh_token)
        token.blacklist()

        return Response(
            {"detail": "LogOut Successful"}, status=status.HTTP_205_RESET_CONTENT
        )
    except Exception as e:
        return Response(
            {"success": "fail", "detail": "LogOut UnSuccessful"},
            status=status.HTTP_400_BAD_REQUEST,
        )


@swagger_auto_schema(
    method="post",
    operation_summary="User Login",
    operation_description="This endpoint allows users to log in using email and password. If the user registered with Google, they must use Google login.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["email", "password"],
        properties={
            "email": openapi.Schema(
                type=openapi.TYPE_STRING,
                format="email",
                description="User's email address",
            ),
            "password": openapi.Schema(
                type=openapi.TYPE_STRING,
                format="password",
                description="User's password",
            ),
        },
    ),
    responses={
        200: openapi.Response(
            description="Login successful",
            examples={
                "application/json": {
                    "refresh": "your-refresh-token",
                    "access": "your-access-token",
                    "user_id": 1,
                    "first_name": "John",
                    "is_company": False,
                }
            },
        ),
        400: openapi.Response(
            description="Validation error",
            examples={
                "application/json": {
                    "email": ["This field is required."],
                    "password": ["This field is required."],
                }
            },
        ),
        401: openapi.Response(
            description="Invalid credentials or email not verified",
            examples={"application/json": {"error": "Invalid email or password"}},
        ),
    },
)
@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data["email"].lower().strip()
        password = serializer.validated_data["password"]  # type: ignore

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "Invalid email or password"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if user.auth_provider == "google":
            return Response({"error": "Use Google login"})
        # if not EmailAddress.objects.get(email=email).verified:
        #     return Response(
        #         {"error": "Email is not verified "}, status=status.HTTP_401_UNAUTHORIZED
        #     )
        try:
            email_entry = EmailAddress.objects.get(email=email)
            if not email_entry.verified:
                return Response(
                    {"error": "Email is not verified"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
        except EmailAddress.DoesNotExist:
            pass

        if check_password(password, user.password):
            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "user_id": user.id,
                    "first_name": user.first_name,
                    "is_company": user.company,
                    "has_onboarded": user.has_onboarded,
                    "is_verified": user.verified,
                    "email": user.email,
                }
            )
        else:
            return Response(
                {"erro": "Invalid email or password"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method="post",
    operation_summary="Verify Email",
    operation_description="Verify a user's email using a unique verification key sent to their email.",
    request_body=EmailVerifySerializer,
    responses={
        200: openapi.Response(
            description="Email successfully verified",
            examples={"application/json": {"detail": "Email verified successfully."}},
        ),
        400: openapi.Response(
            description="Validation error",
            examples={"application/json": {"key": ["This field is required."]}},
        ),
        404: openapi.Response(
            description="Invalid or expired key",
            examples={
                "application/json": {
                    "detail": "Key doesn't exist or Key has been used before"
                }
            },
        ),
    },
)
@api_view(["POST"])
@permission_classes([AllowAny])
def verify_email(request):
    """
    This method verifies the use email exists by Matching the user Unique Key that was sent to the email
    request.data - ['key']
    """
    serialized_data = EmailVerifySerializer(data=request.data)
    if serialized_data.is_valid():
        key = serialized_data.data["key"]
        try:
            unique_key = get_object_or_404(EmailVerication_Keys, key=key)
            if not unique_key:
                return Response(
                    {"detail": _("Key doesn't exist or Key has been used before")},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if unique_key.exp <= timezone.now():
                return Response(
                    {"detail": _("Key has expired.")}, status=status.HTTP_404_NOT_FOUND
                )
            user = unique_key.user
            # Here you can update the 'verified' field of the user
            user.verified = True
            # Because I'm using some of allauth functionalities. I have to update the Email model created by allauth to login
            # Could remove this later
            user_email = EmailAddress.objects.get(email=user.email)
            user_email.verified = True
            user_email.primary = True
            user_email.save()

            user.save()
            # You might also want to delete the used verification key
            unique_key.delete()
            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "user_id": user.id,
                    "first_name": user.first_name,
                    "is_company": user.company,
                    "has_onboarded": user.has_onboarded,
                    "is_Verified": user.verified,
                },
                status=status.HTTP_200_OK,
            )
        except EmailVerication_Keys.DoesNotExist:
            return Response(
                {"detail": _("Invalid verification key.")},
                status=status.HTTP_404_NOT_FOUND,
            )

    return Response(serialized_data.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method="post",
    operation_summary="Request Password Reset",
    operation_description="Accepts an email, checks if it exists in the database, and sends a reset link containing a UID and token.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "email": openapi.Schema(type=openapi.TYPE_STRING, format="email"),
        },
        required=["email"],
    ),
    responses={
        201: openapi.Response(
            description="Password reset link generated",
            examples={
                "application/json": {"detail": {"uid": "some-uid", "key": "some-key"}}
            },
        ),
        400: openapi.Response(
            description="Request failed",
            examples={"application/json": {"errors": "Something went wrong!"}},
        ),
    },
)
@api_view(["POST"])
@permission_classes([AllowAny])
def reset_password(request):
    """
    Receives Email
    Check if Email is in database
    Send (uid, token) in a url
    """
    data = request.data
    if data and "email" in data:
        result = ResetPassword_key(email=data["email"])
        if not result:
            return Response(
                {"errors": "User with this email does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        key, uid = result
        user = get_object_or_404(User, email=data["email"])
        exp = timezone.now() + timezone.timedelta(hours=1)

        # Load and render the HTML email
        template = get_template("password_reset/password_reset.html")
        context = {
            "user": user,
            "key": key,
            "uid": uid,
            "expiry_date": exp.strftime("%Y-%m-%d %H:%M:%S"),
        }
        html = template.render(context)

        # Build params for Resend
        params: resend.Emails.SendParams = {
            "from": "Scuibai <Admin@scuib.com>",
            "to": [user.email],
            "subject": "Reset Your Password",
            "html": html,
        }

        try:
            r = resend.Emails.send(params)
        except Exception as e:
            return Response(
                {"errors": f"Failed to send email: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {"detail": "Password reset link sent to email."},
            status=status.HTTP_200_OK,
        )

    return Response(
        {"errors": "Email is required."},
        status=status.HTTP_400_BAD_REQUEST,
    )


@swagger_auto_schema(
    method="post",
    operation_summary="Confirm Password Reset",
    operation_description="Takes a user ID (uid) and a reset key, along with a new password. If valid, updates the user's password.",
    manual_parameters=[
        openapi.Parameter(
            "uid", openapi.IN_PATH, description="User ID", type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            "key",
            openapi.IN_PATH,
            description="Password reset key",
            type=openapi.TYPE_STRING,
        ),
    ],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "password": openapi.Schema(type=openapi.TYPE_STRING, format="password"),
            "password2": openapi.Schema(type=openapi.TYPE_STRING, format="password"),
        },
        required=["password", "password2"],
    ),
    responses={
        201: openapi.Response(
            description="Password successfully changed",
            examples={"application/json": {"detail": "Password Successfully changed."}},
        ),
        400: openapi.Response(
            description="Passwords do not match",
            examples={"application/json": {"detail": "Passwords do not match."}},
        ),
        404: openapi.Response(
            description="Invalid user or reset key",
            examples={
                "application/json": {
                    "detail": "User DoesNot Exist or Reset Password Key is Invalid"
                }
            },
        ),
    },
)
@api_view(["POST"])
@permission_classes([AllowAny])
def confirm_reset_password(request, uid, key):
    """
    The confirm reset password takes in two arguments
        uid - User id
        key - Key generated from the reset_password
    and the post data
        password
        password2

    Checks if both are valid in the database
        changes the password of the user
    """
    try:
        user = get_object_or_404(User, id=uid)
        if user.auth_provider == "google":
            return Response({"error": "Use Google login"})
        reset_pwd_object = get_object_or_404(PasswordReset_keys, user=user, key=key)

        # Check if key has expired

        if reset_pwd_object.exp <= timezone.now():
            return Response(
                {"detail": _("Key has expired.")}, status=status.HTTP_404_NOT_FOUND
            )

        password = request.data.get("password")
        password2 = request.data.get("password2")

        # Check if passwords match
        if password != password2:
            return Response(
                {"detail": _("Passwords do not match.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update the user's password
        user.set_password(password)
        user.save()

        return Response(
            {"detail": _("Password Successfully changed.")},
            status=status.HTTP_201_CREATED,
        )

    except User.DoesNotExist or PasswordReset_keys.DoesNotExist:
        return Response(
            {"detail": _("User DoesNot Exist or Reset Password Key is Invalid")},
            status=status.HTTP_404_NOT_FOUND,
        )


""" PROFILE VIEWS """


@swagger_auto_schema(
    method="get",
    operation_summary="Get User Profile by ID",
    operation_description="Retrieves the profile details of a user by their ID, including resume, image, skills, and categories.",
    manual_parameters=[
        openapi.Parameter(
            "user_id",
            openapi.IN_PATH,
            description="ID of the user whose profile is to be retrieved",
            type=openapi.TYPE_INTEGER,
            required=True,
        ),
    ],
    responses={
        200: openapi.Response(
            description="Profile data retrieved successfully",
            examples={
                "application/json": {
                    "data": {
                        "email": "user@example.com",
                        "first_name": "John",
                        "last_name": "Doe",
                        "image": "https://example.com/image.jpg",
                        "resume": "https://example.com/resume.pdf",
                        "skills": ["Python", "Django"],
                        "categories": ["Software Development"],
                    }
                }
            },
        ),
        400: openapi.Response(
            description="User ID does not exist",
            examples={"application/json": {"detail": "User Id does not exist"}},
        ),
        404: openapi.Response(
            description="Profile or related data not found",
            examples={"application/json": {"detail": "Not found"}},
        ),
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def profile_detail_by_id(request, user_id):
    """Returns the profile of a user"""
    # Check if user exist
    user = get_object_or_404(User, id=user_id)
    if not user:
        return Response(
            {"detail": "User Id does not exist"}, status=status.HTTP_400_BAD_REQUEST
        )
    # Check if the profile exists
    try:
        profile = Profile.objects.get(user=user)
    except Profile.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    profile_data = DisplayProfileSerializer(profile).data

    return Response({"data": profile_data}, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method="get",
    operation_summary="Get Profile of Authenticated User",
    operation_description="Retrieves the profile details of the currently authenticated user, including resume, image, skills, categories, and notifications.",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    responses={
        200: openapi.Response(
            description="Authenticated user profile retrieved successfully",
            examples={
                "application/json": {
                    "data": {
                        "email": "user@example.com",
                        "first_name": "John",
                        "last_name": "Doe",
                        "image": "https://example.com/image.jpg",
                        "resume": "https://example.com/resume.pdf",
                        "skills": ["Python", "Django"],
                        "categories": ["Software Development"],
                        "notifications": ["New message received"],
                    }
                }
            },
        ),
        404: openapi.Response(
            description="Profile not found",
            examples={"application/json": {"detail": "Not found"}},
        ),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def profile_detail(request):
    # Check if the profile exists
    try:
        profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    profile_data = DisplayProfileSerializer(profile).data
    return Response({"data": profile_data}, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method="get",
    operation_summary="Returns all users notifications",
    operation_description="This endpoint retrieves all notifications of the logged in user",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    responses={
        200: openapi.Response(
            description="Returns all notifications",
        ),
        404: openapi.Response(description="Notification not found"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_notifications(request):
    profile = get_object_or_404(Profile, user=request.user)

    return Response({"data": profile.notifications}, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method="put",
    operation_summary="Update Profile",
    operation_description="Updates the authenticated user's profile. Accepts fields for first name, last name, skills, categories, image, and resume. Note that the email field is not updatable.",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
        openapi.Parameter(
            name="bio",
            in_=openapi.IN_FORM,
            description="Brief description of yourself (optional)",
            type=openapi.TYPE_STRING,
            required=False,
        ),
        openapi.Parameter(
            name="first_name",
            in_=openapi.IN_FORM,
            description="User's first name (optional)",
            type=openapi.TYPE_STRING,
            required=False,
        ),
        openapi.Parameter(
            name="last_name",
            in_=openapi.IN_FORM,
            description="User's Last name (optional)",
            type=openapi.TYPE_STRING,
            required=False,
        ),
        openapi.Parameter(
            name="location",
            in_=openapi.IN_FORM,
            description="User's location (optional)",
            type=openapi.TYPE_STRING,
            required=False,
        ),
        openapi.Parameter(
            name="skills",
            in_=openapi.IN_FORM,
            description="List of skills to update (optional)",
            type=openapi.TYPE_STRING,
            required=False,
        ),
        openapi.Parameter(
            name="categories",
            in_=openapi.IN_FORM,
            description="List of categories to update (optional)",
            type=openapi.TYPE_STRING,
            required=False,
        ),
        openapi.Parameter(
            name="image",
            in_=openapi.IN_FORM,
            description="Profile image file (optional)",
            type=openapi.TYPE_FILE,
            required=False,
        ),
        openapi.Parameter(
            name="resume",
            in_=openapi.IN_FORM,
            description="Resume file (PDF, DOCX, etc.) (optional)",
            type=openapi.TYPE_FILE,
            required=False,
        ),
        openapi.Parameter(
            name="phonenumbers",
            in_=openapi.IN_FORM,
            description="User's phone number (optional)",
            type=openapi.TYPE_STRING,
            required=False,
        ),
        openapi.Parameter(
            name="years_of_experience",
            in_=openapi.IN_FORM,
            description="User's years of experience in number (optional)",
            type=openapi.TYPE_NUMBER,
            required=False,
        ),
        openapi.Parameter(
            name="min_salary",
            in_=openapi.IN_FORM,
            description="User's expected minimum salary in number (optional)",
            type=openapi.TYPE_NUMBER,
            required=False,
        ),
        openapi.Parameter(
            name="max_salary",
            in_=openapi.IN_FORM,
            description="User's expected maximum salary in number (optional)",
            type=openapi.TYPE_NUMBER,
            required=False,
        ),
        openapi.Parameter(
            name="currency",
            in_=openapi.IN_FORM,
            description="User's currency type (optional)",
            type=openapi.TYPE_STRING,
            required=False,
        ),
        openapi.Parameter(
            name="employment_type",
            in_=openapi.IN_FORM,
            description="F: Full-Time, P: Part-Time, C: Contract (optional)",
            type=openapi.TYPE_STRING,
            required=False,
        ),
        openapi.Parameter(
            name="job_location",
            in_=openapi.IN_FORM,
            description="R: Remote, H: Hybrid, O: Onsite (optional)",
            type=openapi.TYPE_STRING,
            required=False,
        ),
        openapi.Parameter(
            name="github",
            in_=openapi.IN_FORM,
            description="User's github url (optional)",
            type=openapi.TYPE_STRING,
            required=False,
        ),
        openapi.Parameter(
            name="linkedin",
            in_=openapi.IN_FORM,
            description="User's linkedin url (optional)",
            type=openapi.TYPE_STRING,
            required=False,
        ),
        openapi.Parameter(
            name="twitter",
            in_=openapi.IN_FORM,
            description="User's twitter url (optional)",
            type=openapi.TYPE_STRING,
            required=False,
        ),
        openapi.Parameter(
            name="portfolio",
            in_=openapi.IN_FORM,
            description="User's portfolio url (optional)",
            type=openapi.TYPE_STRING,
            required=False,
        ),
    ],
    consumes=["multipart/form-data"],
    responses={
        200: openapi.Response(
            description="Profile updated successfully",
            examples={
                "application/json": {
                    "_detail": "Succesful!",
                    "data": {
                        "first_name": "John",
                        "last_name": "Doe",
                        "resume": "https://example.com/resume.pdf",
                        "image": "https://example.com/image.jpg",
                        "skills": ["Python", "Django"],
                        "categories": ["Software Development"],
                    },
                }
            },
        ),
        404: openapi.Response(
            description="Profile does not exist",
            examples={"application/json": {"detail": "Profile does not exist"}},
        ),
        500: openapi.Response(
            description="Internal server error",
            examples={"application/json": {"_detail": "An error occured!"}},
        ),
    },
)
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def profile_update(request):
    user = request.user
    data = request.data.copy()

    # Check if email is in field
    if "email" in data:
        data.pop("email")
    # Check if the profile exists
    try:
        profile = Profile.objects.get(user=user)
    except Profile.DoesNotExist:
        return Response(
            {"detail": "Profile does not exist"}, status=status.HTTP_404_NOT_FOUND
        )

    # Handle first_name and last_name
    user_updated = False
    if "first_name" in data:
        user.first_name = data.pop("first_name")[0]
        user_updated = True
    if "last_name" in data:
        user.last_name = data.pop("last_name")[0]
        user_updated = True
    if user_updated:
        user.save()

    # Handle skill updates
    if "skills" in data:
        new_skills = data.pop("skills")
        new_skills = (
            new_skills if isinstance(new_skills, list) else new_skills.split(",")
        )
        current_skills = set(profile.skills.values_list("name", flat=True))
        new_skills_set = set(new_skills)

        # Add new skills
        for skill_name in new_skills_set - current_skills:
            skill, created = UserSkills.objects.get_or_create(
                name=skill_name, user=request.user
            )
            profile.skills.add(skill)

        # Remove old skills
        for skill_name in current_skills - new_skills_set:
            skill = UserSkills.objects.filter(name=skill_name).first()
            if skill:
                profile.skills.remove(skill)

    # Handle skill updates
    if "categories" in data:
        new_categories = data.pop("categories")
        new_categories = (
            new_categories
            if isinstance(new_categories, list)
            else new_categories.split(",")
        )
        current_categories = set(profile.categories.values_list("name", flat=True))
        new_categories_set = set(new_categories)

        # Add new skills
        for category_name in new_categories_set - current_categories:
            category, created = UserCategories.objects.get_or_create(name=category_name)
            profile.categories.add(category)

        # Remove old skills
        for category_name in current_categories - new_categories_set:
            category = UserCategories.objects.filter(name=category_name).first()
            if category:
                profile.categories.remove(category)

    MAX_FILE_SIZE = 5 * 1024 * 1024
    cloudinary_fields = ["image", "resume", "cover_letter"]
    for field in cloudinary_fields:
        if field in request.FILES:
            uploaded_file = request.FILES[field]

            # Check file size before attempting upload
            if uploaded_file.size > MAX_FILE_SIZE:
                return Response(
                    {"detail": f"{field} exceeds 5MB size limit."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Delete old file if exists
            existing_file = getattr(profile, field)
            if existing_file:
                try:
                    cloudinary.uploader.destroy(existing_file.public_id)
                except Exception as e:
                    print(f"Failed to delete old {field}: {e}")

            # Determine the folder and resource type
            if field == "image":
                folder = "profile_images/"
                resource_type = "image"
            else:  # For resume and cover letter
                folder = "profile_docs/"
                resource_type = "raw"

            file_name, file_ext = os.path.splitext(uploaded_file.name)
            public_id = f"{folder}/{file_name}"

            # Upload new file
            try:
                uploaded_file.seek(0)  # Reset file pointer
                upload_result = cloudinary.uploader.upload(
                    uploaded_file,
                    public_id=public_id,
                    resource_type=resource_type,
                    use_filename=False,
                    unique_filename=False,
                    overwrite=True,
                    format=file_ext.lstrip("."),
                )
                setattr(profile, field, upload_result["public_id"])
                data.pop(field, None)
            except cloudinary.exceptions.Error as e:
                return Response(
                    {"detail": f"Upload failed for {field}: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
    # Save the updated profile
    profile.save()

    # Update profile with the remaining fields
    serialized_data = ProfileSerializer(profile, data=data, partial=True)
    if serialized_data.is_valid():
        serialized_data.save()

        return Response({"detail": "Succesful!"}, status=status.HTTP_200_OK)

    return Response(serialized_data.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method="put",
    operation_summary="Update user onboarding details",
    operation_description="Allows a user to update their profile information, including name, skills, categories, profile image, and resume.",
    manual_parameters=[
        openapi.Parameter(
            "user_id",
            openapi.IN_PATH,
            description="ID of the user whose profile is being updated",
            type=openapi.TYPE_INTEGER,
            required=True,
        ),
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    request_body=ProfileSerializer,
    responses={
        200: openapi.Response(
            description="Profile updated successfully",
            examples={"application/json": {"_detail": "Successful!"}},
        ),
        404: openapi.Response(
            description="User or profile does not exist",
            examples={"application/json": {"detail": "Profile does not exist"}},
        ),
        500: openapi.Response(
            description="An error occurred while updating the profile",
            examples={"application/json": {"_detail": "An error occurred!"}},
        ),
    },
)
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
# @parser_classes([MultiPartParser, FormParser])
def onboarding(request, user_id):
    # Check if the profile exists
    user = get_object_or_404(User, id=user_id)
    print(user)

    data = dict(request.data)
    for f in request.FILES:
        data.pop(f, None)

    try:
        profile = Profile.objects.get(user=user)
    except Profile.DoesNotExist:
        return Response(
            {"detail": "Profile does not exist"}, status=status.HTTP_404_NOT_FOUND
        )

    # Handle user fields (first_name and last_name)
    user_updated = False
    if "first_name" in data:
        user.first_name = data.pop("first_name")[0]
        user_updated = True
    if "last_name" in data:
        user.last_name = data.pop("last_name")[0]
        user_updated = True
    if user_updated:
        user.save()

    # Handle skill updates
    if "skills" in data:
        new_skills = data.pop("skills")
        current_skills = set(profile.skills.values_list("name", flat=True))
        new_skills_set = set(new_skills)

        # Add new skills
        for skill_name in new_skills_set - current_skills:
            skill, created = UserSkills.objects.get_or_create(
                name=skill_name, user=user
            )
            profile.skills.add(skill)

        # Remove old skills
        for skill_name in current_skills - new_skills_set:
            skill = UserSkills.objects.filter(name=skill_name).first()
            if skill:
                profile.skills.remove(skill)

    # Handle skill updates
    if "categories" in data:
        new_categories = data.pop("categories")
        current_categories = set(profile.categories.values_list("name", flat=True))
        new_categories_set = set(new_categories)

        # Add new skills
        for category_name in new_categories_set - current_categories:
            category, created = UserCategories.objects.get_or_create(name=category_name)
            profile.categories.add(category)

        # Remove old skills
        for category_name in current_categories - new_categories_set:
            category = UserCategories.objects.filter(name=category_name).first()
            if category:
                profile.categories.remove(category)

    MAX_FILE_SIZE = 5 * 1024 * 1024
    cloudinary_fields = ["image", "resume"]
    for field in cloudinary_fields:
        if field in request.FILES:
            uploaded_file = request.FILES[field]

            # Check file size before attempting upload
            if uploaded_file.size > MAX_FILE_SIZE:
                return Response(
                    {"detail": f"{field} exceeds 5MB size limit."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Delete old file if exists
            existing_file = getattr(profile, field)
            if existing_file:
                try:
                    cloudinary.uploader.destroy(existing_file.public_id)
                except Exception as e:
                    print(f"Failed to delete old {field}: {e}")

            # Determine the folder and resource type
            if field == "image":
                folder = "profile_images/"
                resource_type = "image"
            else:  # For resume and cover letter
                folder = "profile_docs/"
                resource_type = "raw"

            file_name, file_ext = os.path.splitext(uploaded_file.name)
            public_id = f"{folder}/{file_name}"

            # Upload new file
            try:
                uploaded_file.seek(0)  # Reset file pointer
                upload_result = cloudinary.uploader.upload(
                    uploaded_file,
                    public_id=public_id,
                    resource_type=resource_type,
                    use_filename=False,
                    unique_filename=False,
                    overwrite=True,
                    format=file_ext.lstrip("."),
                )
                setattr(profile, field, upload_result["public_id"])
                data.pop(field, None)
            except cloudinary.exceptions.Error as e:
                return Response(
                    {"detail": f"Upload failed for {field}: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
    profile.save()

    # Update profile with the remaining fields
    serialized_data = ProfileSerializer(profile, data=data, partial=True)
    if serialized_data.is_valid():
        serialized_data.save()
        user.has_onboarded = True
        user.save()

        return Response({"detail": "Succesful!"}, status=status.HTTP_200_OK)

    return Response(serialized_data.errors, status=status.HTTP_400_BAD_REQUEST)


# Delete Authenticated User
@api_view(["GET", "DELETE"])
@permission_classes([IsAuthenticated])
def profile_delete(request):
    """Deletes a User Profile"""
    try:
        # Fetch the profile of the authenticated user
        profile = Profile.objects.get(user=request.user)

        # Delete the profile
        profile.delete()

        # Optionally delete the user account
        user = request.user
        user.delete()

        return Response(
            {"detail": "User and profile deleted successfully."},
            status=status.HTTP_204_NO_CONTENT,
        )
    except Profile.DoesNotExist:
        return Response(
            {"detail": "Profile not found."}, status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


""" JOB VIEWS """


@swagger_auto_schema(
    method="post",
    operation_summary="Create a Job",
    operation_description="This endpoint allows authenticated companies to create a job listing. The system will match the job with suitable applicants using a recommendation system.",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=[
            "title",
            "description",
            "location",
            "experience_level",
            "years_of_experience",
            "skills",
            "employment_type",
        ],
        properties={
            "title": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Job title",
            ),
            "description": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Detailed job description",
            ),
            "experience_level": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Experience level can be Entry, Mid, Senior, Lead",
            ),
            "location": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Job location",
            ),
            "employment_type": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Employment type - O: Onsite, R: Remote, H: Hybrid",
            ),
            "max_salary": openapi.Schema(
                type=openapi.TYPE_NUMBER,
                description="Maximum salary offered",
            ),
            "min_salary": openapi.Schema(
                type=openapi.TYPE_NUMBER,
                description="Minimum salary offered",
            ),
            "years_of_experience": openapi.Schema(
                type=openapi.TYPE_NUMBER,
                description="Years of experience",
            ),
            "currency_type": openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=["USD", "EUR", "NGN", "GBP"],
                description="Currency for salary",
            ),
            "skills": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Items(type=openapi.TYPE_STRING),
                description="List of skills required for the job",
            ),
        },
    ),
    responses={
        201: openapi.Response(
            description="Job successfully created",
            examples={
                "application/json": {
                    "detail": "Job successfully posted!",
                    "data": {
                        "job_id": 1,
                        "owner_id": 12,
                        "company_name": "TechCorp",
                        "company_email": "contact@techcorp.com",
                        "skills": ["Python", "Django"],
                        "category": "Software Development",
                        "title": "Backend Developer",
                        "description": "Develop and maintain APIs",
                        "location": "Remote",
                        "employment_type": "Full-time",
                        "max_salary": 80000,
                        "min_salary": 50000,
                        "currency_type": "USD",
                        "recommended_applicants": [
                            {
                                "user_id": 34,
                                "user_name": "Jane Doe",
                                "user_email": "janedoe@example.com",
                                "match_score": 85.7,
                                "years_of_experience": 5,
                                "salary_range": "50K-80K",
                                "location": "New York",
                                "skills": ["Python", "Django"],
                            }
                        ],
                    },
                }
            },
        ),
        400: openapi.Response(
            description="Bad request",
            examples={
                "application/json": {
                    "error": "Invalid job data",
                }
            },
        ),
        404: openapi.Response(
            description="User is not a company",
            examples={
                "application/json": {
                    "error": "Only Companies can create Jobs",
                }
            },
        ),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def job_create(request):
    user = request.user

    if not user.company:
        return Response(
            "Only Companies can create Jobs", status=status.HTTP_404_NOT_FOUND
        )

    request.data["owner"] = user.id

    # Extract skills from request
    new_skills = request.data.pop("skills", [])

    # Serialize and save job data
    serialized_data = JobSerializer(data=request.data)

    if serialized_data.is_valid():
        job_instance = serialized_data.save()

        # Create and associate job skills
        for skill in new_skills:
            job_skill, created = JobSkills.objects.get_or_create(name=skill)
            job_instance.skills.add(job_skill)

        return Response(
            {
                "detail": _("Job successfully posted!"),
                "job_id": job_instance.id,
            },
            status=status.HTTP_201_CREATED,
        )
    return Response(
        {"error": serialized_data.errors}, status=status.HTTP_400_BAD_REQUEST
    )


@swagger_auto_schema(
    method="get",
    operation_summary="Get Job recommendation",
    operation_description="This endpoint allows authenticated companies to get matching applicants based on their job",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    responses={
        201: openapi.Response(
            description="Job successfully created",
            examples={
                "application/json": {
                    "detail": "Job successfully posted!",
                    "recommended_applicants": [
                        {
                            "user_id": 34,
                            "user_name": "Jane Doe",
                            "user_email": "janedoe@example.com",
                            "match_score": 85.7,
                            "years_of_experience": 5,
                            "salary_range": "50K-80K",
                            "location": "New York",
                            "skills": ["Python", "Django"],
                        }
                    ],
                },
            },
        ),
        400: openapi.Response(
            description="Bad request",
            examples={
                "application/json": {
                    "error": "Invalid job id",
                }
            },
        ),
        404: openapi.Response(
            description="Not Found",
            examples={
                "application/json": {
                    "error": "Not found",
                }
            },
        ),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_recommendation(request, job_id):
    user = request.user

    # Use the recommendation system to find suitable applicants
    matcher = JobAppMatching()

    job_data = matcher.load_job_from_db(job_id)

    if not job_data:
        return Response(
            {"error": "Job data could not be retrieved."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Convert job data into Pandas DataFrame format
    job_df = pd.DataFrame([job_data])

    matcher.enrich_jobs_with_currency(job_df)
    # Load all users as potential candidates

    user_profiles = matcher.load_users_from_db()

    if user_profiles.empty or user_profiles["skills"].str.strip().eq("").all():
        return Response(
            {
                "recommended_applicants": [],
            },
            status=status.HTTP_200_OK,
        )

    # Get matching applicants using the recommendation function
    recommended_users = matcher.recommend_users(job_data, user_profiles)

    recommended_applicants_list = []

    # Fetch all profiles in one go, including related data
    user_ids = [u["user_id"] for u in recommended_users]
    profiles = (
        Profile.objects.filter(user_id__in=user_ids)
        .select_related("user")  # optimize user join
        .prefetch_related("skills")  # optimize M2M fetch
    )

    # Map for O(1) access
    profile_map = {p.user_id: p for p in profiles}

    for user_data in recommended_users:
        user_id = user_data["user_id"]
        profile = profile_map.get(user_id)
        if not profile:
            continue

        recommended_applicants_list.append(
            {
                "user_id": profile.user.id,
                "user_name": profile.user.first_name,
                "user_email": profile.user.email,
                "User_bio": profile.bio,
                "image": profile.image.url if profile.image else None,
                "match_score": user_data["match_score"],
                "years_of_experience": profile.years_of_experience,
                "salary_range": user_data["salary_range"],
                "currency": profile.currency,
                "location": profile.location,
                "employment_choice": profile.employment_type,
                "job_location_choice": profile.job_location,
                "skills": list(profile.skills.values_list("name", flat=True)),
            }
        )

    return Response(
        {
            "recommended_applicants": recommended_applicants_list,
        },
        status=status.HTTP_200_OK,
    )


@swagger_auto_schema(
    method="put",
    operation_summary="Update a Job",
    operation_description="This endpoint allows the job owner to update a job listing, including its details and skills.",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "title": openapi.Schema(
                type=openapi.TYPE_STRING, description="Updated job title"
            ),
            "description": openapi.Schema(
                type=openapi.TYPE_STRING, description="Updated job description"
            ),
            "location": openapi.Schema(
                type=openapi.TYPE_STRING, description="Updated job location"
            ),
            "employment_type": openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=["Full-time", "Part-time", "Contract", "Remote"],
                description="Updated employment type",
            ),
            "max_salary": openapi.Schema(
                type=openapi.TYPE_NUMBER, description="Updated max salary"
            ),
            "min_salary": openapi.Schema(
                type=openapi.TYPE_NUMBER, description="Updated min salary"
            ),
            "currency_type": openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=["USD", "EUR", "NGN", "GBP"],
                description="Updated currency type",
            ),
            "skills": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Items(type=openapi.TYPE_STRING),
                description="Updated list of skills required for the job",
            ),
        },
    ),
    responses={
        200: openapi.Response(
            description="Job successfully updated",
            examples={
                "application/json": {
                    "detail": "Job Successfully updated!",
                    "data": {
                        "job_id": 1,
                        "title": "Updated Backend Developer",
                        "description": "Updated API maintenance tasks",
                        "location": "Remote",
                        "employment_type": "Contract",
                        "max_salary": 90000,
                        "min_salary": 60000,
                        "currency_type": "USD",
                        "skills": ["Python", "Django", "FastAPI"],
                    },
                }
            },
        ),
        403: openapi.Response(
            description="Unauthorized action",
            examples={
                "application/json": {
                    "error": "You do not have permission to update this job"
                }
            },
        ),
        400: openapi.Response(
            description="Bad request",
            examples={"application/json": {"error": "Invalid update data"}},
        ),
    },
)
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def job_update(request, job_id):
    user = request.user
    job_instance = get_object_or_404(Jobs, id=job_id)

    if job_instance.owner != user:
        return Response(
            "You do not have permission to update this job",
            status=status.HTTP_403_FORBIDDEN,
        )

    skills_update = "skills" in request.data
    new_skills = request.data.pop("skills", [])

    serialized_data = JobSerializer(job_instance, data=request.data, partial=True)
    if serialized_data.is_valid():
        serialized_data.save()

        if skills_update:
            current_skills = set(job_instance.skills.values_list("name", flat=True))
            new_skills_set = set(new_skills)

            # Add new skills
            for skill_name in new_skills_set - current_skills:
                skill = JobSkills.objects.filter(name=skill_name).first()
                if not skill:
                    skill = JobSkills.objects.create(name=skill_name)
                job_instance.skills.add(skill)
                job_instance.save()

            # Remove old skills
            for skill_name in current_skills - new_skills_set:
                skills_to_remove = JobSkills.objects.filter(name=skill_name).distinct()
                job_instance.skills.remove(*skills_to_remove)
                job_instance.save()

            job_created.send(sender=Jobs, instance=job_instance)

        data = serialized_data.data
        return Response(
            {"detail": _("Job Successfully updated!"), "data": data},
            status=status.HTTP_200_OK,
        )

    return Response(serialized_data.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method="get",
    operation_summary="Returns all jobs in the database",
    operation_description="This endpoint retrieves all jobs posted. No authentication required",
    responses={
        200: openapi.Response(
            description="Returns all jobs",
        ),
        404: openapi.Response(description="Job not found"),
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def jobs_all(request):
    cleanup_old_jobs()
    jobs = Jobs.objects.all()
    serialized_jobs = JobSerializer(jobs, many=True)
    return Response(serialized_jobs.data, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method="get",
    operation_summary="Returns all jobs created by a user with applicants list",
    operation_description="This returns all the jobs created by the loggedin company and displays the matches for the job",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    responses={
        201: openapi.Response(
            description="Jobs retrieved",
            examples={
                "data": {
                    "job_id": 1,
                    "owner_id": 12,
                    "company_name": "TechCorp",
                    "company_email": "contact@techcorp.com",
                    "skills": ["Python", "Django"],
                    "category": "Software Development",
                    "title": "Backend Developer",
                    "description": "Develop and maintain APIs",
                    "location": "Remote",
                    "employment_type": "Full-time",
                    "max_salary": 80000,
                    "min_salary": 50000,
                    "currency_type": "USD",
                    "recommended_applicants": [
                        {
                            "user_id": 34,
                            "user_name": "Jane Doe",
                            "user_email": "janedoe@example.com",
                            "match_score": 85.7,
                            "years_of_experience": 5,
                            "salary_range": "50K-80K",
                            "location": "New York",
                            "skills": ["Python", "Django"],
                        }
                    ],
                },
            },
        ),
        400: openapi.Response(
            description="Bad request",
            examples={
                "application/json": {
                    "error": "Invalid job data",
                }
            },
        ),
        404: openapi.Response(
            description="User is not a company",
            examples={
                "application/json": {
                    "error": "Only Companies can create Jobs",
                }
            },
        ),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def jobs_user(request):
    user = request.user
    jobs = Jobs.objects.filter(owner=user)
    data = []

    for job in jobs:
        # Get all Applicant entries for this job
        applicants = Applicant.objects.filter(job=job).select_related("user__profile")

        # Build job data
        job_data = {
            "job": {
                "job_id": job.id,
                "title": job.title,
                "description": job.description,
                "location": job.location,
                "role": list(job.categories.values_list("name", flat=True)),
                "type": job.employment_type,
                "skills": list(job.skills.values_list("name", flat=True)),
                "pay_range": f"{job.min_salary} - {job.max_salary}",
                "experience": job.experience_level,
                "employment_type": job.get_employment_type_display(),
                "created_at": job.created_at,
            },
            "applicants": [],
        }

        # Build applicants list
        for applicant in applicants:
            applicant_user = applicant.user
            profile = getattr(applicant_user, "profile", None)  # Safe profile access

            # Skip users without profiles
            if not profile:
                continue

            applicant_data = {
                "applicant_id": applicant_user.id,
                "first_name": applicant_user.first_name,
                "last_name": applicant_user.last_name or "",
                "email": applicant_user.email,
                "phonenumber": profile.phonenumbers,
                "user_bio": profile.bio,
                "location": profile.location,
                "job_location_choice": profile.job_location,
                "image": profile.image.url if profile.image else None,
                "skills": list(profile.skills.values_list("name", flat=True)),
                "categories": list(profile.categories.values_list("name", flat=True)),
                "experience": profile.years_of_experience,
                "match_score": applicant.match_score,
            }
            job_data["applicants"].append(applicant_data)

        data.append(job_data)

    return Response(data, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method="delete",
    operation_summary="Deletes a job by id",
    operation_description="Allows a company to delete its job post",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    responses={
        204: openapi.Response(
            description="Job deleted successfully",
        ),
        404: openapi.Response(description="Job not found"),
    },
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_job(request, job_id):
    job = Jobs.objects.get(id=job_id)
    # Check if job exists
    if not job:
        return Response(
            {"detail": f"Job {job_id} does not exist"}, status=status.HTTP_404_NOT_FOUND
        )

    # Check if the authenticated user is the owner of job post
    if not request.user.id == job.owner.id:
        return Response(
            {"detail": f"User is not permitted to delete this job"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    job.delete()
    return Response({"detail": "Job deleted Successfully"}, status=status.HTTP_200_OK)


from django.core.exceptions import ObjectDoesNotExist


@swagger_auto_schema(
    method="get",
    operation_summary="Retrieve company details",
    operation_description="Fetches the details of the authenticated user's company profile.",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    responses={
        200: CompanySerializer,
        404: openapi.Response("CompanyProfile not found."),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def company(request):
    """Get the company's details"""
    owner = request.user
    try:
        company = CompanyProfile.objects.get(owner=owner)
        serializer = CompanySerializer(company)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except ObjectDoesNotExist:
        return Response(
            {"error": "CompanyProfile not found."}, status=status.HTTP_404_NOT_FOUND
        )


@swagger_auto_schema(
    method="put",
    operation_summary="Update company details",
    operation_description="Allows the authenticated user to update their company profile details.",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
        openapi.Parameter(
            name="company_name",
            in_=openapi.IN_FORM,
            description="Name of the company",
            type=openapi.TYPE_STRING,
            required=False,
        ),
        openapi.Parameter(
            name="address",
            in_=openapi.IN_FORM,
            description="Address of the company",
            type=openapi.TYPE_STRING,
            required=False,
        ),
        openapi.Parameter(
            name="website",
            in_=openapi.IN_FORM,
            description="Website of the company",
            type=openapi.TYPE_STRING,
            required=False,
        ),
        openapi.Parameter(
            name="description",
            in_=openapi.IN_FORM,
            description="Short description of the company",
            type=openapi.TYPE_STRING,
            required=False,
        ),
        openapi.Parameter(
            name="phone_number",
            in_=openapi.IN_FORM,
            description="Phone number of the company",
            type=openapi.TYPE_STRING,
            required=False,
        ),
        openapi.Parameter(
            name="image",
            in_=openapi.IN_FORM,
            description="Profile image (file upload)",
            type=openapi.TYPE_FILE,
            required=False,
        ),
    ],
    consumes=["multipart/form-data"],
    responses={
        200: openapi.Response(
            description="Profile updated successfully",
            examples={"application/json": {"_detail": "Successful!"}},
        ),
        404: openapi.Response(
            description="User or profile does not exist",
            examples={"application/json": {"detail": "Profile does not exist"}},
        ),
        500: openapi.Response(
            description="An error occurred while updating the profile",
            examples={"application/json": {"_detail": "An error occurred!"}},
        ),
    },
)
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def company_update(request):
    user = request.user
    try:
        company_profile = CompanyProfile.objects.get(owner=user)
    except CompanyProfile.DoesNotExist:
        return Response(
            {"error": "Company profile not found."}, status=status.HTTP_404_NOT_FOUND
        )

    if request.user.id != company_profile.owner.id:
        return Response(
            {"error": "You do not have permission to edit this profile."},
            status=status.HTTP_403_FORBIDDEN,
        )
    serializer = CompanyProfileSerializer(
        company_profile, data=request.data, partial=True
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Handle image AFTER validation
    if "image" in request.FILES:
        # Validate file
        image_file = request.FILES["image"]
        if image_file.size > 5 * 1024 * 1024:  # 5MB limit
            return Response({"error": "File too large"}, status=400)
        # Delete old image
        existing_file = getattr(company_profile, "image", None)
        if existing_file:
            try:
                cloudinary.uploader.destroy(existing_file.public_id)
            except Exception as e:
                print(f"Failed to delete old image: {e}")

        # Upload new image
        upload_result = cloudinary.uploader.upload(
            image_file,
            folder="company_profile",
            resource_type="image",
        )
        company_profile.image = upload_result["secure_url"]
        company_profile.save()

    # Save other fields
    serializer.save()
    user.has_onboarded = True
    user.save()
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_user(request):
    user = request.user
    user.delete()
    return Response({"detail": "User deleted Successfully"}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
def waitlist(request):
    email = request.data.get("email")  # Use .get() to avoid KeyError

    if not email:
        return Response(
            {"detail": "Email is required"}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        waitlist_entry = WaitList(email=email)
        waitlist_entry.save()
        return Response({"detail": "Successful"}, status=status.HTTP_201_CREATED)
    except Exception as e:
        # Log the exception if needed
        return Response(
            {"detail": "Unsuccessful", "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@swagger_auto_schema(
    method="get",
    operation_summary="Returns all users in the database. Restricted to only admin users",
    operation_description="This endpoint retrieves all users in the database for the admin user to see.",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    responses={
        200: openapi.Response(
            description="Returns all Users",
        ),
        404: openapi.Response(description="Users not found"),
    },
)
@api_view(["GET"])
@permission_classes([IsAdminUser])
def list_users(request):
    users = User.objects.all()
    serializer = DisplayUsers(users, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method="get",
    operation_summary="Get Profile of All Users By Admin",
    operation_description="Allows an admin user to retrieve the profile details of all users",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    responses={
        200: openapi.Response(
            description="Returns a list of all user profiles in the database",
            examples={
                "application/json": {
                    "data": {
                        "email": "user@example.com",
                        "first_name": "John",
                        "last_name": "Doe",
                        "image": "https://example.com/image.jpg",
                        "resume": "https://example.com/resume.pdf",
                        "skills": ["Python", "Django"],
                        "categories": ["Software Development"],
                        "notifications": ["New message received"],
                    }
                }
            },
        ),
        404: openapi.Response(
            description="Profile not found",
            examples={"application/json": {"detail": "Not found"}},
        ),
    },
)
@api_view(["GET"])
@permission_classes([IsAdminUser])
def all_profiles(request):
    """Returns the profiles of all users in the database"""
    users = Profile.objects.all()
    serializer = DisplayProfileSerializer(users, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method="delete",
    operation_summary="Delete a User by Admin",
    operation_description="Allows an admin to delete a user by providing the user's ID.",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
        openapi.Parameter(
            name="user_id",
            in_=openapi.IN_PATH,
            description="ID of the user to delete",
            type=openapi.TYPE_INTEGER,
            required=True,
        ),
    ],
    responses={
        204: openapi.Response(
            description="User successfully deleted",
        ),
        404: openapi.Response(
            description="User not found",
            examples={"application/json": {"detail": "User not found"}},
        ),
        400: openapi.Response(
            description="Bad Request",
            examples={"application/json": {"detail": "Missing user_id parameter"}},
        ),
    },
)
@api_view(["DELETE"])
@permission_classes([IsAdminUser])
def delete_user_by_admin(request, user_id):
    """Allows an admin to delete a user by ID"""
    user = get_object_or_404(User, id=user_id)
    user.delete()
    return Response(
        {"detail": "User deleted successfully"},
        status=status.HTTP_204_NO_CONTENT,
    )


@swagger_auto_schema(
    method="post",
    operation_summary="Google Login",
    operation_description="This endpoint allows users to log in via google.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["token"],
        properties={
            "token": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Token retrieved from google auth",
            ),
        },
    ),
    responses={
        200: openapi.Response(
            description="Login successful",
            examples={
                "application/json": {
                    "refresh": "your-refresh-token",
                    "access": "your-access-token",
                    "user_id": 1,
                    "first_name": "John",
                    "is_company": False,
                }
            },
        ),
        400: openapi.Response(
            description="Validation error",
            examples={
                "application/json": {
                    "token": ["This field is required."],
                }
            },
        ),
        401: openapi.Response(
            description="Invalid credentials",
            examples={"application/json": {"error": "Invalid token"}},
        ),
    },
)
@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def google_auth(request):
    """Takes a google auth token, verifies it and login the user"""
    serializer = GoogleAuthSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    email = serializer.validated_data["email"]
    first_name = serializer.validated_data["first_name"]
    last_name = serializer.validated_data["last_name"]
    try:
        user = User.objects.get(email=email)
        # if user.auth_provider != "google":
        #     return Response(
        #         {"error": "Please login using your email and password"},
        #         status=status.HTTP_401_UNAUTHORIZED,
        #     )
    except User.DoesNotExist:
        user_data = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "password": settings.SOCIAL_SECRET_KEY,
            "password2": settings.SOCIAL_SECRET_KEY,
        }

        user_serializer = UserSerializer(data=user_data)
        if user_serializer.is_valid():
            user = user_serializer.save()
            user.verified = True
            user.auth_provider = "google"
            EmailAddress.objects.create(
                user=user, email=user.email, verified=True, primary=True
            )
            user.save()
        else:
            return Response(user_serializer.errors, status=400)

    # Generate tokens
    refresh = RefreshToken.for_user(user)
    return Response(
        {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user_id": user.id,
            "first_name": user.first_name,
            "is_company": user.company,
            "has_onboarded": user.has_onboarded,
            "is_verified": user.verified,
            "email": user.email,
        },
        status=status.HTTP_200_OK,
    )


@swagger_auto_schema(
    method="post",
    operation_summary="Post a Job without Authentication and get recommendations",
    operation_description="Allows users to post a job without authentication and receive a list of recommended applicants.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=[
            "location",
            "experience_level",
            "years_of_experience",
            "skills",
            "salary",
            "currency_type",
        ],
        properties={
            "experience_level": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Experience level can be entry, mid, senior, lead",
            ),
            "location": openapi.Schema(
                type=openapi.TYPE_STRING, description="Job location"
            ),
            "years_of_experience": openapi.Schema(
                type=openapi.TYPE_NUMBER,
                description="Minimum years of experience needed for the job",
            ),
            "max_salary": openapi.Schema(
                type=openapi.TYPE_NUMBER, description="Maximum salary"
            ),
            "min_salary": openapi.Schema(
                type=openapi.TYPE_NUMBER, description="Minimum salary"
            ),
            "currency_type": openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=["USD", "EUR", "NGN", "GBP"],
                description="Salary currency",
            ),
            "skills": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Items(type=openapi.TYPE_STRING),
                description="Required skills",
            ),
        },
    ),
    responses={
        200: openapi.Response(
            description="Recommended applicants",
            examples={
                "application/json": {
                    "detail": "Job processed successfully!",
                    "recommended_applicants": [
                        {
                            "user_id": 34,
                            "user_name": "Jane Doe",
                            "user_email": "janedoe@example.com",
                            "match_score": 85.7,
                            "years_of_experience": 5,
                            "salary_range": "50K-80K",
                            "location": "New York",
                            "skills": ["Python", "Django"],
                        }
                    ],
                }
            },
        ),
        400: openapi.Response(
            description="Bad request",
            examples={"application/json": {"error": "Invalid job data"}},
        ),
    },
)
@api_view(["POST"])
def post_job_without_auth(request):
    job_data = request.data
    job_data["skills"] = ";".join(job_data["skills"])
    # Prepare data for recommendation system
    job_df = pd.DataFrame([job_data])

    # Instantiate recommendation system
    matcher = JobAppMatching()

    # Enrich job data
    matcher.enrich_jobs_with_currency(job_df)

    # Load all users as potential candidates
    user_profiles = matcher.load_users_from_db()

    if user_profiles.empty or user_profiles["skills"].str.strip().eq("").all():
        return Response(
            {
                "detail": "Job processed successfully!",
                "recommended_applicants": [],
            },
            status=status.HTTP_200_OK,
        )

    # Get top 5 matching applicants
    recommended_users = matcher.recommend_users(job_data, user_profiles)

    recommended_applicants_list = []

    # Fetch all profiles in one go, including related data
    user_ids = [u["user_id"] for u in recommended_users]
    profiles = (
        Profile.objects.filter(user_id__in=user_ids)
        .select_related("user")  # optimize user join
        .prefetch_related("skills")  # optimize M2M fetch
    )

    # Map for O(1) access
    profile_map = {p.user_id: p for p in profiles}

    for user_data in recommended_users:
        user_id = user_data["user_id"]
        profile = profile_map.get(user_id)
        if not profile:
            continue

        recommended_applicants_list.append(
            {
                "user_id": profile.user.id,
                "user_name": profile.user.first_name,
                "user_email": profile.user.email,
                "User_bio": profile.bio,
                "image": profile.image.url if profile.image else None,
                "match_score": user_data["match_score"],
                "years_of_experience": profile.years_of_experience,
                "salary_range": user_data["salary_range"],
                "currency": profile.currency,
                "location": profile.location,
                "employment_choice": profile.employment_type,
                "job_location_choice": profile.job_location,
                "skills": list(profile.skills.values_list("name", flat=True)),
            }
        )

    return Response(
        {
            "detail": "Job processed successfully!",
            "recommended_applicants": recommended_applicants_list,
        },
        status=status.HTTP_200_OK,
    )


@swagger_auto_schema(
    method="post",
    operation_summary="Job post with categories matching wuthout authentication",
    operation_description="Allows users to post a job without authentication and receive a list of recommended applicants based on categories.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=[
            "location",
            "experience_level",
            "years_of_experience",
            "categories",
            "salary",
            "currency_type",
        ],
        properties={
            "experience_level": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Experience level can be entry, mid, senior, lead",
            ),
            "location": openapi.Schema(
                type=openapi.TYPE_STRING, description="Job location"
            ),
            "years_of_experience": openapi.Schema(
                type=openapi.TYPE_NUMBER,
                description="Minimum years of experience needed for the job",
            ),
            "max_salary": openapi.Schema(
                type=openapi.TYPE_NUMBER, description="Maximum salary"
            ),
            "min_salary": openapi.Schema(
                type=openapi.TYPE_NUMBER, description="Minimum salary"
            ),
            "currency_type": openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=["USD", "EUR", "NGN", "GBP"],
                description="Salary currency",
            ),
            "categories": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Items(type=openapi.TYPE_STRING),
                description="Required categories",
            ),
        },
    ),
    responses={
        200: openapi.Response(
            description="Recommended applicants",
            examples={
                "application/json": {
                    "detail": "Job processed successfully!",
                    "recommended_applicants": [
                        {
                            "user_id": 34,
                            "user_name": "Jane Doe",
                            "user_email": "janedoe@example.com",
                            "match_score": 85.7,
                            "years_of_experience": 5,
                            "salary_range": "50K-80K",
                            "location": "New York",
                            "categories": ["Backend Developer", "UI Designer"],
                        }
                    ],
                }
            },
        ),
        400: openapi.Response(
            description="Bad request",
            examples={"application/json": {"error": "Invalid job data"}},
        ),
    },
)
@api_view(["POST"])
def match_job_with_categories(request):
    job_data = request.data
    job_data["categories"] = ";".join(job_data["categories"])
    # Prepare data for recommendation system
    job_df = pd.DataFrame([job_data])

    # Instantiate recommendation system
    matcher = JobAppMatching()

    # Enrich job data
    matcher.enrich_jobs_with_currency(job_df)

    # Load all users as potential candidates
    user_profiles = matcher.load_users_from_db()

    if user_profiles.empty or user_profiles["skills"].str.strip().eq("").all():
        return Response(
            {
                "recommended_applicants": [],
            },
            status=status.HTTP_200_OK,
        )

    # Get top 5 matching applicants
    recommended_users = matcher.recommend_users_categories(job_data, user_profiles)

    recommended_applicants_list = []

    # Fetch all profiles in one go, including related data
    user_ids = [u["user_id"] for u in recommended_users]
    profiles = (
        Profile.objects.filter(user_id__in=user_ids)
        .select_related("user")  # optimize user join
        .prefetch_related("skills")  # optimize M2M fetch
    )

    # Map for O(1) access
    profile_map = {p.user_id: p for p in profiles}

    for user_data in recommended_users:
        user_id = user_data["user_id"]
        profile = profile_map.get(user_id)
        if not profile:
            continue

        recommended_applicants_list.append(
            {
                "user_id": profile.user.id,
                "user_name": profile.user.first_name,
                "user_email": profile.user.email,
                "User_bio": profile.bio,
                "image": profile.image.url if profile.image else None,
                "match_score": user_data["match_score"],
                "years_of_experience": profile.years_of_experience,
                "salary_range": user_data["salary_range"],
                "currency": profile.currency,
                "location": profile.location,
                "employment_choice": profile.employment_type,
                "job_location_choice": profile.job_location,
                "categories": list(profile.categories.values_list("name", flat=True)),
            }
        )
    return Response(
        {
            "recommended_applicants": recommended_applicants_list,
        },
        status=status.HTTP_200_OK,
    )


@swagger_auto_schema(
    method="patch",
    operation_summary="Update the 'company' field of the user",
    operation_description="Allows an authenticated user to update their 'company' field. The field accepts boolean values (true or false) or null.",
    manual_parameters=[
        openapi.Parameter(
            "Authorization",
            openapi.IN_HEADER,
            description="Bearer Token for authentication",
            type=openapi.TYPE_STRING,
            required=True,
        )
    ],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["company"],
        properties={
            "company": openapi.Schema(
                type=openapi.TYPE_BOOLEAN,
                description="Set to true if the user is a company, false otherwise.",
            )
        },
    ),
    responses={
        200: openapi.Response(
            "Company status updated successfully.",
            openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "detail": openapi.Schema(type=openapi.TYPE_STRING),
                    "company": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                },
            ),
        ),
        400: openapi.Response("Bad Request: Missing or invalid company field."),
        401: openapi.Response("Unauthorized: User must be authenticated."),
    },
)
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_company_status(request):
    user = request.user

    if "company" not in request.data:
        return Response(
            {"detail": "company field is required."}, status=status.HTTP_400_BAD_REQUEST
        )

    company = request.data["company"]

    if not isinstance(company, bool) and company is not None:
        return Response(
            {"detail": "company must be a boolean or null."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.company = company
    user.save()

    return Response(
        {"detail": "Company status updated successfully.", "company": user.company},
        status=status.HTTP_200_OK,
    )


@swagger_auto_schema(
    method="get",
    operation_summary="Get Profile Name and Picture only",
    operation_description="Returns the profile picture and name of the authenticated user",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    responses={
        200: openapi.Response(
            description="Authenticated user profile retrieved successfully",
            examples={
                "application/json": {
                    "data": {
                        "first_name": "John",
                        "last_name": "Doe",
                        "image": "https://example.com/image.jpg",
                    }
                }
            },
        ),
        404: openapi.Response(
            description="Profile not found",
            examples={"application/json": {"detail": "Not found"}},
        ),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def profile_header(request):
    # Check if the profile exists
    try:
        user = User.objects.get(id=request.user.id)
        if not user.company:
            profile = Profile.objects.get(user=user)
            data = {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "profile_pic": profile.image.url if profile.image else None,
            }
        else:
            company = CompanyProfile.objects.get(owner=user)
            data = {
                "company_name": company.company_name,
                "profile_pic": company.image.url if company.image else None,
            }
    except User.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    return Response(data, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method="post",
    operation_summary="Get Message from the Frontend",
    operation_description="Receive message from the frontend and send it to the admin user",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["name", "email", "message"],
        properties={
            "name": openapi.Schema(
                type=openapi.TYPE_STRING, description="Name of the sender"
            ),
            "email": openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_EMAIL,
                description="Email of the sender",
            ),
            "message": openapi.Schema(
                type=openapi.TYPE_STRING, description="Message content"
            ),
        },
    ),
    responses={
        200: openapi.Response(description="Message sent successfully."),
        400: openapi.Response(description="Missing or invalid fields."),
        500: openapi.Response(description="Failed to send message."),
    },
)
@api_view(["POST"])
@permission_classes([AllowAny])
def contact_us(request):
    name = request.data.get("name")
    email = request.data.get("email")
    message = request.data.get("message")

    if not name or not email or not message:
        return Response(
            {"detail": "Name, email, and message are required."}, status=400
        )

    # Render the HTML email using a Django template
    template = get_template("contact/contact_email.html")
    context = {
        "name": name,
        "email": email,
        "message": message,
    }
    html = template.render(context)

    params: resend.Emails.SendParams = {
        "from": "Scuibai <admin@scuib.com>",
        "to": ["scuib.com@gmail.com", "okpephillips.dev@gmail.com"],
        "subject": f"New Contact Form Message from {name}",
        "html": html,
    }

    try:
        resend.Emails.send(params)
        return Response(
            {"detail": "Message sent successfully!"}, status=status.HTTP_200_OK
        )
    except Exception as e:
        print(f"Contact form error: {e}")
        return Response(
            {"detail": "Failed to send message. Please try again."}, status=500
        )


@swagger_auto_schema(
    method="get",
    operation_summary="Count users in the database by Admin",
    operation_description="Allows an admin to know how many users are on the platform.",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    responses={
        204: openapi.Response(
            description="Count of users in the database",
        ),
        404: openapi.Response(
            description="No users found",
            examples={"application/json": {"detail": "Users not found"}},
        ),
    },
)
@api_view(["GET"])
@permission_classes([IsAdminUser])
def count_users(request):
    """Allows an admin to delete a user by ID"""
    users = User.objects.all()
    count = 0
    recruiters = 0
    applicants = 0
    admin = 0
    for user in users:
        count += 1
        if user.company:
            recruiters += 1
        else:
            applicants += 1
        if user.is_staff:
            admin += 1
        if not user.company and user.is_staff:
            applicants -= 1
        if user.company and user.is_staff:
            recruiters -= 1

    return Response(
        {
            "count": count,
            "recruiters": recruiters,
            "applicants": applicants,
            "admin": admin,
        },
        status=status.HTTP_200_OK,
    )


skills_param = openapi.Schema(
    type=openapi.TYPE_ARRAY,
    items=openapi.Items(type=openapi.TYPE_STRING),
    description="List of skills to match (any match)",
    example=["Django", "React"],
)
categories_param = openapi.Schema(
    type=openapi.TYPE_ARRAY,
    items=openapi.Items(type=openapi.TYPE_STRING),
    description="Category to match",
    example=["Backend", "Frontend"],
)

location_param = openapi.Schema(
    type=openapi.TYPE_STRING,
    description="Exact location to match (case-insensitive)",
    example="Lagos",
)

request_body_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "skills": skills_param,
        "location": location_param,
    },
    required=["skills", "location"],
)
request_body_schema_category = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "categories": categories_param,
        "location": location_param,
    },
    required=["categories", "location"],
)

response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "detail": openapi.Schema(type=openapi.TYPE_STRING),
        "recommended_applicants": openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "user_id": openapi.Schema(type=openapi.TYPE_INTEGER),
                    "user_name": openapi.Schema(type=openapi.TYPE_STRING),
                    "user_email": openapi.Schema(type=openapi.TYPE_STRING),
                    "User_bio": openapi.Schema(type=openapi.TYPE_STRING),
                    "image": openapi.Schema(
                        type=openapi.TYPE_STRING, format="uri", nullable=True
                    ),
                    "location": openapi.Schema(type=openapi.TYPE_STRING),
                    "Employment_choice": openapi.Schema(type=openapi.TYPE_STRING),
                    "job_location_choice": openapi.Schema(type=openapi.TYPE_STRING),
                    "skills": openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Items(type=openapi.TYPE_STRING),
                    ),
                },
            ),
        ),
    },
)


@swagger_auto_schema(
    method="post",
    operation_summary="Recommend Users by Skills and Location (Any Skill Match)",
    operation_description="""
    Recommend users who match at least one of the specified skills and exactly match the provided location.
    """,
    request_body=request_body_schema,
    responses={200: response_schema, 400: "Bad Request", 500: "Server Error"},
)
@api_view(["POST"])
@permission_classes([AllowAny])
def recommend_users_by_skills_and_location(request):
    """
    Recommends users who match any of the provided skills and location.
    """
    try:
        job_data = request.data
        skills = job_data.get("skills", [])
        location = job_data.get("location", "")

        if not skills or not location:
            return Response(
                {"error": "All fields are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Instantiate recommendation system helper
        matcher = JobAppMatching()
        user_profiles = matcher.load_users_from_db()
        if user_profiles.empty:
            return Response(
                {
                    "detail": "No users available for recommendation.",
                    "recommended_applicants": [],
                },
                status=status.HTTP_200_OK,
            )

        # Use the "match any skills" logic
        recommended_users = matcher.recommend_users_any_skills(
            skills, location, user_profiles
        )
        matched_users = []
        user_ids = [u["user_id"] for u in recommended_users]
        profiles = Profile.objects.select_related("user").filter(user_id__in=user_ids)
        profile_map = {p.user_id: p for p in profiles}
        for user_data in recommended_users:
            try:
                user_id = user_data["user_id"]
                profile = profile_map.get(user_id)
                matched_users.append(
                    {
                        "user_id": profile.user.id,
                        "user_name": profile.user.first_name,
                        "user_email": profile.user.email,
                        "User_bio": profile.bio,
                        "image": profile.image.url if profile.image else None,
                        "years_of_experience": profile.years_of_experience,
                        "location": profile.location,
                        "Employment_choice": profile.employment_type,
                        "job_location_choice": profile.job_location,
                        "skills": list(profile.skills.values_list("name", flat=True)),
                    }
                )

            except Profile.DoesNotExist:
                continue

        return Response(
            {
                "detail": "Users matched successfully!",
                "matched_users": matched_users,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return Response(
            {"error": f"Something went wrong: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@swagger_auto_schema(
    method="post",
    operation_summary="Boost Message to selected users",
    operation_description="This endpoint allows a recruiter to send messaege to selected users that match their requirements",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["title", "content", "recipients"],
        properties={
            "title": openapi.Schema(
                type=openapi.TYPE_STRING, description="Title of the message"
            ),
            "content": openapi.Schema(
                type=openapi.TYPE_STRING, description="Content of the message"
            ),
            "recipients_id": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Items(type=openapi.TYPE_NUMBER),
                description="List of user_ids of recipients of the message",
                example=[24, 5],
            ),
        },
    ),
    responses={
        200: "Boost message sent!",
        400: "Bad request. All fields are required",
        401: "Unauthorized",
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def message_boost(request):
    """Sends a boost message to selected users"""
    try:
        data = request.data
        recipients_id = data.get("recipients_id", [])
        title = data.get("title")
        content = data.get("content")
        sender = request.user

        if not recipients_id or not title or not content:
            return Response(
                {"error": "All fields are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create a unique boost ID
        boost_id = str(uuid.uuid4())[:8]  # Short unique ID

        # Create chat thread
        thread = BoostChatThread.objects.create(boost_id=boost_id, recruiter=sender)

        profiles = Profile.objects.select_related("user").filter(
            user_id__in=recipients_id
        )
        profile_map = {p.user_id: p for p in profiles}
        for user_id in recipients_id:
            profile = profile_map.get(user_id)
            if not profile:
                continue

            # Create message linked to thread
            Message.objects.create(
                user=profile.user,
                title=title,
                sender=sender,
                content=content,
                boost_id=boost_id,
                thread=thread,
            )
            # Add recipient to chat participants
            thread.participants.add(profile.user)

        return Response(
            {
                "detail": "Message sent successfully!",
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return Response(
            {"error": f"Something went wrong: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@swagger_auto_schema(
    method="post",
    operation_summary="Post message in Boost chat",
    operation_description="This endpoint allows users to post messages in the chat room",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "content": openapi.Schema(
                type=openapi.TYPE_STRING, description="Content of the message"
            ),
            "parent_id": openapi.Schema(
                type=openapi.TYPE_NUMBER, description="ID of parent message"
            ),
        },
    ),
    responses={
        200: "Boost message sent!",
        400: "Bad request. All fields are required",
        401: "Unauthorized",
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def post_boost_chat_message(request, boost_id):
    """Send a chat message under a boost thread."""
    user = request.user
    content = request.data.get("content")
    parent_id = request.data.get("parent_id")

    if not content:
        return Response({"detail": "Message content required"}, status=400)

    thread = get_object_or_404(BoostChatThread, boost_id=boost_id)

    # Recruiter or unlocked users can send
    is_recruiter = thread.recruiter == user
    is_unlocked = BoostUnlock.objects.filter(boost_id=boost_id, user=user).exists()
    has_subscription = BoostSubscription.objects.filter(
        user=user, active=True, end_date__gte=timezone.now()
    ).exists()

    if not (is_recruiter or is_unlocked or has_subscription):
        return Response({"detail": "You cannot post in this chat."}, status=403)

    parent_message = None
    if parent_id:
        parent_message = get_object_or_404(
            Message,
            id=parent_id,
            thread=thread,
        )

    message = Message.objects.create(
        user=user,
        sender=user,
        thread=thread,
        parent=parent_message,
        title=f"Chat - Boost {boost_id}",
        content=content,
        unlocked=is_unlocked,
    )

    thread.participants.add(user)

    serializer = MessageSerializer(message, context={"request": request})

    return Response(
        {
            "detail": "Message sent successfully",
            "message": serializer.data,
        },
        status=201,
    )


@swagger_auto_schema(
    method="get",
    operation_summary="List user messages with preview if locked",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    responses={200: MessageSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_boost_chat_messages(request, boost_id):
    """Get all chat messages for a boost thread."""
    user = request.user
    thread = get_object_or_404(BoostChatThread, boost_id=boost_id)

    is_recruiter = thread.recruiter == user
    is_unlocked = BoostUnlock.objects.filter(boost_id=boost_id, user=user).exists()
    has_subscription = BoostSubscription.objects.filter(
        user=user, active=True, end_date__gte=timezone.now()
    ).exists()

    messages = thread.messages.filter(parent__isnull=True).order_by("created_at")

    # Restrict view for users who haven't unlocked
    if not (is_recruiter or is_unlocked or has_subscription):
        messages = messages[:2]  # Show only first 2 messages

    serializer = MessageSerializer(messages, many=True, context={"request": request})

    return Response(
        {
            "messages": serializer.data,
            "is_unlocked": is_unlocked,
        }
    )


@swagger_auto_schema(
    method="post",
    operation_summary="Fund Wallet",
    operation_description="Initializes a Paystack transaction and returns authorization URL for payment.",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["amount"],
        properties={
            "amount": openapi.Schema(
                type=openapi.TYPE_NUMBER, description="Amount in Naira"
            )
        },
    ),
    responses={200: "Authorization URL returned"},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def fund_wallet(request):
    """
    Initializes a Paystack payment and returns authorization URL.
    """
    amount = request.data.get("amount")
    if not amount:
        return Response({"error": "Amount is required."}, status=400)

    reference = generate_reference()
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "email": request.user.email,
        "amount": int(float(amount) * 100),  # Paystack requires kobo
        "reference": reference,
        "callback_url": "https://scuib.com/payment/verify",  # Optional
    }

    response = requests.post(
        "https://api.paystack.co/transaction/initialize", json=data, headers=headers
    )
    result = response.json()

    if result.get("status") is True:
        # Save the transaction (pending)
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        WalletTransaction.objects.create(
            wallet=wallet,
            amount=amount,
            type="deposit",
            reference=reference,
            status="pending",
            source="wallet",
            description="Paystack funding initialized",
        )

        return Response(
            {"auth_url": result["data"]["authorization_url"], "reference": reference}
        )
    else:
        return Response(
            {"error": result.get("message", "Payment initialization failed.")},
            status=400,
        )


@swagger_auto_schema(
    method="get",
    operation_summary="Verify Payment",
    operation_description="Verifies a Paystack transaction using reference and credits wallet.",
    manual_parameters=[
        openapi.Parameter(
            "reference",
            openapi.IN_PATH,
            description="Transaction reference",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    responses={200: "Wallet funded successfully"},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def verify_payment(request, reference):
    """
    Verifies payment from Paystack and updates wallet.
    """
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
    }

    response = requests.get(
        f"https://api.paystack.co/transaction/verify/{reference}", headers=headers
    )
    result = response.json()

    if result.get("status") is True and result["data"]["status"] == "success":
        amount_paid = Decimal(result["data"]["amount"]) / 100  # Convert to naira

        wallet = Wallet.objects.filter(user=request.user).first()

        if not wallet:
            return Response({"error": "Wallet not found."}, status=404)

        txn = WalletTransaction.objects.filter(
            wallet=wallet, reference=reference
        ).first()

        if not txn:
            return Response({"error": "Transaction not found."}, status=404)

        if txn.status == "success":
            return Response({"message": "Transaction already verified."})

        wallet.balance += amount_paid
        wallet.save()

        txn.status = "success"
        txn.description = "Wallet funded via Paystack"
        txn.save()

        return Response(
            {"message": "Wallet funded successfully!", "balance": wallet.balance}
        )

    return Response(
        {"error": "Verification failed or transaction not successful."}, status=400
    )


@swagger_auto_schema(
    method="get",
    operation_summary="Get Wallet Balance",
    operation_description="Returns current wallet balance for authenticated user.",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    responses={200: "Balance returned"},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def wallet_balance(request):
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    return Response({"balance": wallet.balance})


@swagger_auto_schema(
    method="get",
    operation_summary="Unlock Full Message",
    operation_description=f"Deducts ₦{UNLOCK_COST} from wallet to unlock full message by message ID.",
    manual_parameters=[
        openapi.Parameter(
            "message_id",
            openapi.IN_PATH,
            description="ID of the message",
            type=openapi.TYPE_INTEGER,
        ),
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    responses={
        200: openapi.Response("Message content unlocked."),
        402: "Insufficient funds",
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def unlock_message(request, message_id):
    try:
        message = Message.objects.get(id=message_id, user=request.user)
        boost_id = message.boost_id

        if not boost_id:
            return Response(
                {"detail": "This message is not linked to a boost."}, status=400
            )

        if BoostUnlock.objects.filter(boost_id=boost_id, user=request.user).exists():
            sender_data = (
                UserSerializer(message.sender).data if message.sender else None
            )

            return Response(
                {
                    "detail": "Boost chat unlocked successfully!",
                    "boost_id": boost_id,
                    "message": message.content,
                    "sender": sender_data,
                }
            )

        wallet = Wallet.objects.get(user=request.user)
        if not wallet.deduct(UNLOCK_COST, f"Unlocked boost chat {boost_id}"):
            return Response({"detail": "Insufficient wallet balance."}, status=402)

        BoostUnlock.objects.create(boost_id=boost_id, user=request.user)

        # Mark the message as unlocked for backward compatibility
        message.unlocked = True
        message.is_read = True
        message.save(update_fields=["unlocked", "is_read"])

        sender_data = UserSerializer(message.sender).data if message.sender else None

        return Response(
            {
                "detail": "Boost chat unlocked successfully!",
                "boost_id": boost_id,
                "message": message.content,
                "sender": sender_data,
            }
        )

    except Message.DoesNotExist:
        return Response({"detail": "Message not found."}, status=404)


@swagger_auto_schema(
    method="get",
    operation_summary="List user messages with preview if locked",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    responses={200: MessageSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_messages(request):
    cleanup_messages()
    messages = (
        Message.objects.filter(parent__isnull=True, thread__participants=request.user)
        .select_related("sender", "thread")
        .prefetch_related("replies")
        .order_by("-created_at")
    )
    serializer = MessageSerializer(messages, many=True, context={"request": request})
    return Response(serializer.data)


@swagger_auto_schema(
    method="get",
    operation_summary="List messages that the user sent",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    responses={200: MessageSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sent_messages(request):
    messages = Message.objects.filter(sender=request.user).order_by("-created_at")
    serializer = SentMessageSerializer(messages, many=True)
    return Response(serializer.data)


@swagger_auto_schema(
    method="delete",
    operation_summary="Delete a message",
    operation_description="Allows a logged in user to delete a message by id.",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
        openapi.Parameter(
            name="message_id",
            in_=openapi.IN_PATH,
            description="ID of the message to delete",
            type=openapi.TYPE_INTEGER,
            required=True,
        ),
    ],
    responses={
        204: openapi.Response(
            description="Deleted",
        ),
        404: openapi.Response(
            description="Message not found",
            examples={"application/json": {"detail": "Message not found"}},
        ),
        400: openapi.Response(
            description="Bad Request",
            examples={"application/json": {"detail": "Missing message_id parameter"}},
        ),
    },
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_message(request, message_id):
    message = get_object_or_404(Message, id=message_id)
    message.delete()
    return Response(
        {"detail": "Message deleted successfully"},
        status=status.HTTP_204_NO_CONTENT,
    )


@swagger_auto_schema(
    method="get",
    operation_summary="Transaction History shows all debit and credit activities of the user",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    responses={200: WalletTransactionSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def transaction_history(request):
    transactions = WalletTransaction.objects.filter(wallet__user=request.user).order_by(
        "-created_at"
    )
    serializer = WalletTransactionSerializer(transactions, many=True)
    return Response(serializer.data)


@swagger_auto_schema(
    method="post",
    operation_summary="Returns twitter jobs scraped",
    responses={200: JobTweetSerializer(many=True)},
)
@api_view(["POST"])
@permission_classes([AllowAny])
def fetch_twitter_jobs(limit=50):
    """Fetch jobs from twitter via scraping"""
    query = "#hiring OR #remotejobs OR #techjobs lang:en"
    tweets = sntwitter.TwitterSearchScraper(query).get_items()

    new_jobs = []
    for i, tweet in enumerate(tweets):
        if i >= limit:
            break

        data = {
            "tweet_id": tweet.id,
            "user_id": tweet.user.username,
            "text": tweet.content,
            "created_at": tweet.date,
            "tweet_link": f"https://twitter.com/{tweet.user.username}/status/{tweet.id}",
        }

        # Save only new tweets
        if not JobTweet.objects.filter(tweet_id=tweet.id).exists():
            job = JobTweet(**data)
            job.save()
            new_jobs.append(job)

    serializer = JobTweetSerializer(new_jobs, many=True)
    return Response({"fetched": len(new_jobs), "jobs": serializer.data})


@swagger_auto_schema(
    method="post",
    operation_summary="Recommend Users by Category and Location (Any Category Match)",
    operation_description="""
    Recommend users who match at least one of the specified categories and exactly match the provided location.
    """,
    request_body=request_body_schema_category,
    responses={200: response_schema, 400: "Bad Request", 500: "Server Error"},
)
@api_view(["POST"])
@permission_classes([AllowAny])
def recommend_users_by_categories_and_location(request):
    """
    Recommends users who match any of the provided categories and location.
    Categories are stored as text in Job model.
    """
    try:
        job_data = request.data
        categories = job_data.get("categories", [])  # expecting a list of categories
        location = job_data.get("location", "")

        if not categories or not location:
            return Response(
                {"error": "All fields are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Instantiate recommendation system helper
        matcher = JobAppMatching()
        user_profiles = matcher.load_users_from_db()
        if user_profiles.empty:
            return Response(
                {
                    "detail": "No users available for recommendation.",
                    "matched_users": [],
                },
                status=status.HTTP_200_OK,
            )

        # Use the "match any categories" logic
        recommended_users = matcher.recommend_users_any_categories(
            categories, location, user_profiles
        )

        matched_users = []
        user_ids = [u["user_id"] for u in recommended_users]
        profiles = Profile.objects.select_related("user").filter(user_id__in=user_ids)
        profile_map = {p.user_id: p for p in profiles}

        for user_data in recommended_users:
            try:
                user_id = user_data["user_id"]
                profile = profile_map.get(user_id)
                matched_users.append(
                    {
                        "user_id": profile.user.id,
                        "user_name": profile.user.first_name,
                        "user_email": profile.user.email,
                        "user_bio": profile.bio,
                        "image": profile.image.url if profile.image else None,
                        "years_of_experience": profile.years_of_experience,
                        "location": profile.location,
                        "employment_choice": profile.employment_type,
                        "job_location_choice": profile.job_location,
                        "categories": list(
                            profile.categories.values_list("name", flat=True)
                        ),
                    }
                )
            except Profile.DoesNotExist:
                continue

        return Response(
            {
                "detail": "Users matched successfully!",
                "matched_users": matched_users,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return Response(
            {"error": f"Something went wrong: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@swagger_auto_schema(
    method="post",
    operation_summary="Create a Job (Category-based Matching)",
    operation_description="This endpoint allows authenticated companies to create a job listing. The system will match the job with suitable applicants using CATEGORIES instead of skills.",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=[
            "title",
            "description",
            "location",
            "experience_level",
            "years_of_experience",
            "categories",
            "employment_type",
        ],
        properties={
            "title": openapi.Schema(type=openapi.TYPE_STRING, description="Job title"),
            "description": openapi.Schema(
                type=openapi.TYPE_STRING, description="Job description"
            ),
            "experience_level": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Experience level (Entry, Mid, Senior, Lead)",
            ),
            "location": openapi.Schema(
                type=openapi.TYPE_STRING, description="Job location"
            ),
            "employment_type": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Employment type - O: Onsite, R: Remote, H: Hybrid",
            ),
            "max_salary": openapi.Schema(
                type=openapi.TYPE_NUMBER, description="Maximum salary offered"
            ),
            "min_salary": openapi.Schema(
                type=openapi.TYPE_NUMBER, description="Minimum salary offered"
            ),
            "years_of_experience": openapi.Schema(
                type=openapi.TYPE_NUMBER, description="Years of experience"
            ),
            "currency_type": openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=["USD", "EUR", "NGN", "GBP"],
                description="Currency for salary",
            ),
            "categories": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Items(type=openapi.TYPE_STRING),
                description="List of categories required for the job",
            ),
        },
    ),
    responses={
        201: openapi.Response(
            description="Job successfully created with category-based matching",
        ),
        400: openapi.Response(description="Invalid job data"),
        404: openapi.Response(description="User is not a company"),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def job_create_with_categories(request):
    user = request.user

    if not user.company:
        return Response(
            {"error": "Only Companies can create Jobs"},
            status=status.HTTP_404_NOT_FOUND,
        )

    request.data["owner"] = user.id

    # Extract categories from request
    new_categories = request.data.pop("categories", [])

    serialized_data = JobSerializer(data=request.data)

    if serialized_data.is_valid():
        job_instance = serialized_data.save()

        # Create and associate job categories
        for cat in new_categories:
            job_cat, _ = UserCategories.objects.get_or_create(name=cat)
            job_instance.categories.add(job_cat)

        # Get job categories
        job_categories = list(job_instance.categories.values_list("name", flat=True))

        data = {
            "job_id": job_instance.id,
            "owner_id": job_instance.owner.id,
            "company_name": job_instance.owner.first_name,
            "company_email": job_instance.owner.email,
            "categories": job_categories,
            "title": job_instance.title,
            "description": job_instance.description,
            "location": job_instance.location,
            "employment_type": job_instance.employment_type,
            "max_salary": job_instance.max_salary,
            "min_salary": job_instance.min_salary,
            "currency_type": job_instance.currency_type,
        }

        matcher = JobAppMatching()

        job_data = matcher.load_job_from_db(job_instance.id)
        if not job_data:
            return Response(
                {"error": "Job data could not be retrieved."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        job_df = pd.DataFrame([job_data])
        matcher.enrich_jobs_with_currency(job_df)

        user_profiles = matcher.load_users_from_db()
        if user_profiles.empty or user_profiles["categories"].str.strip().eq("").all():
            return Response(
                {
                    "detail": "Job successfully posted!",
                    "data": data,
                    "recommended_applicants": [],
                },
                status=status.HTTP_201_CREATED,
            )

        # Get matches by categories (instead of skills)
        recommended_users = matcher.recommend_users_categories(job_data, user_profiles)

        recommended_applicants_list = []
        user_ids = [u["user_id"] for u in recommended_users]
        profiles = (
            Profile.objects.filter(user_id__in=user_ids)
            .select_related("user")  # optimize user join
            .prefetch_related("skills")  # optimize M2M fetch
        )

        # Map for O(1) access
        profile_map = {p.user_id: p for p in profiles}

        for user_data in recommended_users:
            user_id = user_data["user_id"]
            profile = profile_map.get(user_id)
            if not profile:
                continue
            recommended_applicants_list.append(
                {
                    "user_id": profile.user.id,
                    "user_name": profile.user.first_name,
                    "user_email": profile.user.email,
                    "user_bio": profile.bio,
                    "image": profile.image.url if profile.image else None,
                    "match_score": user_data["match_score"],
                    "years_of_experience": profile.years_of_experience,
                    "salary_range": user_data["salary_range"],
                    "currency": profile.currency,
                    "location": profile.location,
                    "employment_choice": profile.employment_type,
                    "job_location_choice": profile.job_location,
                    "categories": list(
                        profile.categories.values_list("name", flat=True)
                    ),
                }
            )

        data["recommended_applicants"] = recommended_applicants_list

        return Response(
            {"detail": "Job successfully posted!", "data": data},
            status=status.HTTP_201_CREATED,
        )

    return Response(
        {"error": serialized_data.errors}, status=status.HTTP_400_BAD_REQUEST
    )


@swagger_auto_schema(
    method="put",
    operation_summary="Edit a boost chat message",
    operation_description="Allows the sender to edit their own boost chat message",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["content"],
        properties={"content": openapi.Schema(type=openapi.TYPE_STRING)},
    ),
    responses={
        200: "Message updated successfully",
        403: "You can only edit your own messages",
        404: "Message not found",
    },
)
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def edit_boost_chat_message(request, message_id):
    user = request.user
    new_content = request.data.get("content")

    if not new_content:
        return Response({"detail": "New content is required"}, status=400)

    message = get_object_or_404(Message, id=message_id)

    # Owner check
    if message.user != user:
        return Response({"detail": "You can only edit your own messages"}, status=403)

    message.content = new_content
    message.save()

    return Response(
        {
            "detail": "Message updated successfully",
            "message": {
                "id": message.id,
                "content": message.content,
                "updated_at": message.updated_at,
            },
        },
        status=200,
    )


@swagger_auto_schema(
    method="delete",
    operation_summary="Delete a boost chat message",
    operation_description="Allows the sender to delete their own message",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    responses={
        200: "Message deleted",
        403: "Permission denied",
        404: "Message not found",
    },
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_boost_chat_message(request, message_id):
    user = request.user
    message = get_object_or_404(Message, id=message_id)

    # Only owner can delete
    if message.user != user:
        return Response({"detail": "You can only delete your own message"}, status=403)

    message.delete()

    return Response({"detail": "Message deleted successfully"}, status=200)


@swagger_auto_schema(
    method="post",
    operation_summary="Subscribe to Boost Messages",
    operation_description="Authenticated user  subscribes to the boost plan they want.",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["plan"],
        properties={
            "plan": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Subscription plan: weekly or monthly",
            )
        },
    ),
    responses={
        200: openapi.Response(
            description="Subscription activated successfully",
            examples={
                "application/json": {
                    "detail": "Subscription activated",
                    "expires": "2025-03-30T12:45:00Z",
                }
            },
        ),
        400: openapi.Response(
            description="Invalid plan",
            examples={"application/json": {"detail": "Invalid plan"}},
        ),
        402: openapi.Response(
            description="Insufficient wallet balance",
            examples={"application/json": {"detail": "Insufficient wallet balance"}},
        ),
        401: openapi.Response(
            description="Unauthorized",
            examples={
                "application/json": {
                    "detail": "Authentication credentials were not provided"
                }
            },
        ),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def subscribe_to_boost(request):
    user = request.user
    plan = request.data.get("plan")

    PRICES = {
        "weekly": Decimal("1500"),
        "monthly": Decimal("6000"),
    }

    DURATIONS = {
        "weekly": 7,
        "monthly": 30,
    }

    if plan not in PRICES:
        return Response({"detail": "Invalid plan"}, status=400)

    wallet = Wallet.objects.get(user=user)
    cost = PRICES[plan]
    duration = DURATIONS[plan]

    # Deduct from wallet
    success = wallet.deduct(cost, description=f"Boost {plan} subscription")

    if not success:
        return Response({"detail": "Insufficient wallet balance"}, status=402)

    # Activate / Extend subscription
    now = timezone.now()

    subscription, created = BoostSubscription.objects.get_or_create(
        user=user,
        defaults={
            "plan": plan,
            "start_date": now,
            "end_date": now + timedelta(days=duration),
            "active": True,
        },
    )

    if not created and subscription.end_date > now:
        subscription.end_date += timedelta(days=duration)
    else:
        subscription.start_date = now
        subscription.end_date = now + timedelta(days=duration)
        subscription.active = True

    subscription.plan = plan
    subscription.save()

    return Response(
        {"detail": "Subscription activated", "expires": subscription.end_date},
        status=200,
    )


@swagger_auto_schema(
    method="get",
    operation_summary="Get Subscription status",
    operation_description="Authenticated user gets subscription status",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    responses={
        200: openapi.Response(
            description="Subscription activated successfully",
            examples={
                "application/json": {
                    "active": True,
                    "plan": "monthly",
                    "expires": "2025-12-30T14:22:10Z",
                }
            },
        ),
        401: openapi.Response(
            description="Unauthorized",
            examples={
                "application/json": {
                    "detail": "Authentication credentials were not provided"
                }
            },
        ),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_subscription(request):
    try:
        sub = BoostSubscription.objects.get(user=request.user)
        return Response(
            {
                "active": bool(sub.is_active()),
                "plan": str(sub.plan),
                "expires": sub.end_date,
            }
        )
    except BoostSubscription.DoesNotExist:
        return Response({"active": False})


@swagger_auto_schema(
    method="post",
    operation_summary="Post a Boost Job",
    operation_description="This endpoint allows authenticated user to create a boost job listing.",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=[
            "title",
            "description",
            "job_type",
            "job_nature",
            "location",
            "experience_level",
            "min_salary",
            "max_salary",
            "application_link",
        ],
        properties={
            "title": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Job title",
            ),
            "description": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Detailed job description",
            ),
            "application_link": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="URL to apply for the job",
            ),
            "experience_level": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Experience level can be Entry, Mid, Senior, Lead",
            ),
            "location": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Job location",
            ),
            "job_nature": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Job nature - Onsite, Remote, Hybrid",
            ),
            "max_salary": openapi.Schema(
                type=openapi.TYPE_NUMBER,
                description="Maximum salary offered",
            ),
            "min_salary": openapi.Schema(
                type=openapi.TYPE_NUMBER,
                description="Minimum salary offered",
            ),
            "job_type": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="JOb type: Full-time, part-time, internship, etc",
            ),
        },
    ),
    responses={
        201: openapi.Response(
            description="Job successfully created",
        ),
        400: openapi.Response(
            description="Bad request",
            examples={
                "application/json": {
                    "error": "Invalid job data",
                }
            },
        ),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def post_boost_job(request):
    serializer = BoostJobSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method="get",
    operation_summary="Get All Boost Jobs",
    operation_description="Get all boost Jobs",
    responses={
        200: openapi.Response(
            description="Successful",
        ),
        404: openapi.Response(
            description="Not Found",
            examples={"application/json": {"detail": "Boost Job not found"}},
        ),
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def all_boost_jobs(request):
    jobs = BoostJobs.objects.all().order_by("-created_at")
    serializer = BoostJobSerializer(jobs, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method="get",
    operation_summary="Get Job boost",
    operation_description="Get Boost Job ny id",
    responses={
        200: openapi.Response(
            description="Successful",
        ),
        404: openapi.Response(
            description="Not Found",
            examples={"application/json": {"detail": "Boost Job not found"}},
        ),
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def retrieve_boost_job(request, job_id):
    try:
        job = BoostJobs.objects.get(id=job_id)
    except BoostJobs.DoesNotExist:
        return Response({"detail": "Job not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = BoostJobSerializer(job)
    return Response(serializer.data, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method="put",
    operation_summary="Edit a Boost Job",
    operation_description="This endpoint allows authenticated user to edit a boost job listing.",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "title": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Job title",
            ),
            "description": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Detailed job description",
            ),
            "application_link": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="URL to apply for the job",
            ),
            "experience_level": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Experience level can be Entry, Mid, Senior, Lead",
            ),
            "location": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Job location",
            ),
            "job_nature": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Job nature - Onsite, Remote, Hybrid",
            ),
            "max_salary": openapi.Schema(
                type=openapi.TYPE_NUMBER,
                description="Maximum salary offered",
            ),
            "min_salary": openapi.Schema(
                type=openapi.TYPE_NUMBER,
                description="Minimum salary offered",
            ),
            "job_type": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="JOb type: Full-time, part-time, internship, etc",
            ),
        },
    ),
    responses={
        201: openapi.Response(
            description="Job updated successfully created",
        ),
        400: openapi.Response(
            description="Bad request",
            examples={
                "application/json": {
                    "error": "Invalid job data",
                }
            },
        ),
    },
)
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_boost_job(request, job_id):
    try:
        job = BoostJobs.objects.get(id=job_id)
    except BoostJobs.DoesNotExist:
        return Response({"detail": "Job not found"}, status=404)

    # Only owner or admin can edit
    if job.owner != request.user and not request.user.is_staff:
        return Response(
            {"detail": "You are not allowed to edit this job"},
            status=403,
        )

    serializer = JobSerializer(job, data=request.data, partial=True)

    if serializer.is_valid():
        serializer.save()
        return Response(
            {"message": "Job updated successfully", "data": serializer.data}
        )

    return Response(serializer.errors, status=400)


@swagger_auto_schema(
    method="delete",
    operation_summary="Delete a Job boost",
    operation_description="Delete Boost Job by id",
    responses={
        204: openapi.Response(
            description="Successful",
        ),
        404: openapi.Response(
            description="Not Found",
            examples={"application/json": {"detail": "Boost Job not found"}},
        ),
    },
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_boost_job(request, job_id):
    try:
        job = BoostJobs.objects.get(id=job_id)
    except BoostJobs.DoesNotExist:
        return Response({"detail": "Job not found"}, status=404)

    if job.owner != request.user and not request.user.is_staff:
        return Response(
            {"detail": "You are not allowed to delete this job"},
            status=403,
        )

    job.delete()
    return Response({"message": "Job deleted successfully"})


@swagger_auto_schema(
    method="post",
    operation_summary="Set or Update Job Preferences",
    operation_description="This endpoint allows an authenticated user to create or update their job preferences for job matching.",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "preferred_job_types": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Items(type=openapi.TYPE_STRING),
                description="List of preferred job types such as Full-time, Part-time, Internship, Contract",
            ),
            "preferred_job_nature": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Items(type=openapi.TYPE_STRING),
                description="Preferred job mode such as Remote, Onsite, Hybrid",
            ),
            "preferred_locations": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Items(type=openapi.TYPE_STRING),
                description="Preferred job locations. Can include multiple cities or countries",
            ),
            "preferred_categories": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Items(type=openapi.TYPE_STRING),
                description="List of categories the user is interested in",
            ),
            "preferred_experience": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Experience level. e.g Entry, Mid, Senior",
            ),
            "min_salary": openapi.Schema(
                type=openapi.TYPE_NUMBER,
                description="Minimum expected salary",
            ),
            "max_salary": openapi.Schema(
                type=openapi.TYPE_NUMBER,
                description="Maximum expected salary",
            ),
        },
    ),
    responses={
        200: openapi.Response(
            description="Preferences saved successfully",
            examples={
                "application/json": {
                    "message": "Preferences updated successfully",
                    "data": {
                        "preferred_job_types": ["Full-time", "Contract"],
                        "preferred_job_nature": ["Remote", "Hybrid"],
                        "preferred_locations": ["Lagos", "Abuja", "London"],
                        "preferred_experience": "Mid",
                        "min_salary": 200000,
                        "max_salary": 800000,
                        "preferred_categories": ["Backend Developer"],
                    },
                }
            },
        ),
        400: openapi.Response(
            description="Bad request",
            examples={
                "application/json": {
                    "error": "Invalid preference data",
                }
            },
        ),
    },
)
@api_view(["POST", "PUT"])
@permission_classes([IsAuthenticated])
def job_preference_view(request):
    user = request.user

    try:
        pref = JobPreference.objects.get(user=user)
    except JobPreference.DoesNotExist:
        pref = None

    if request.method == "GET":
        if not pref:
            return Response({"detail": "No preference set yet"}, status=404)

        serializer = JobPreferenceSerializer(pref)
        return Response(serializer.data)

    # PUT / PATCH → Create or Update
    if pref:
        serializer = JobPreferenceSerializer(
            pref,
            data=request.data,
            partial=True if request.method == "PATCH" else False,
        )
    else:
        serializer = JobPreferenceSerializer(data=request.data)

    if serializer.is_valid():
        obj = serializer.save(user=user) if not pref else serializer.save()
        return Response(
            {
                "message": "Preferences saved successfully",
                "data": JobPreferenceSerializer(obj).data,
            }
        )

    return Response(serializer.errors, status=400)


@swagger_auto_schema(
    method="get",
    operation_summary="Get Recommended Boost Jobs",
    operation_description="Returns jobs recommended for the authenticated user based on their saved preferences.",
    manual_parameters=[
        openapi.Parameter(
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
    ],
    responses={
        200: openapi.Response(description="Recommended jobs retrieved successfully"),
        404: openapi.Response(description="Preferences not set"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def recommended_boost_jobs(request):
    user = request.user

    try:
        preference = user.job_preference
    except JobPreference.DoesNotExist:
        preference = None

    # If no preferences → return all boost jobs
    if not preference:
        jobs = BoostJobs.objects.all().order_by("-created_at")

        data = [
            {
                "id": job.id,
                "title": job.title,
                "location": job.location,
                "job_type": job.job_type,
                "job_nature": job.job_nature,
                "experience_level": job.experience_level,
                "min_salary": job.min_salary,
                "max_salary": job.max_salary,
                "application_link": job.application_link,
                "score": None,
            }
            for job in jobs
        ]

        return Response({"results": data})

    matcher = JobAppMatching()

    recommendations = matcher.recommend_boost_jobs_for_user_preferences(preference)

    data = [
        {
            "id": job.id,
            "title": job.title,
            "location": job.location,
            "job_type": job.job_type,
            "job_nature": job.job_nature,
            "experience_level": job.experience_level,
            "min_salary": job.min_salary,
            "max_salary": job.max_salary,
            "application_link": job.application_link,
            "score": score,
        }
        for job, score in recommendations
    ]

    return Response({"results": data})
