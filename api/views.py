import requests
import cloudinary.uploader
from django.shortcuts import render, get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from uuid import uuid4
import cloudinary
from django.core.mail import EmailMultiAlternatives
import pandas as pd
import json

from .models import (
    CompanyProfile,
    Profile,
    User,
    EmailVerication_Keys,
    Assists,
    Subscription,
    PasswordReset_keys,
    JobSkills,
    UserCategories,
    UserSkills,
    WaitList,
    JobSkills,
    Cover_Letter,
    Resume,
    Image,
    Jobs,
    Applicants,
)

from .serializer import (
    CompanySerializer,
    DisplayProfileSerializer,
    MyTokenObtainPairSerializer,
    UserSerializer,
    ProfileSerializer,
    EmailVerifySerializer,
    ApplicantSerializer,
    LoginSerializer,
    ResumeSerializer,
    ImageSerializer,
    CoverLetterSerializer,
    JobSerializer,
    CompanySerializer,
    DisplayUsers,
    GoogleAuthSerializer,
)

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .tools import VerifyEmail_key, ResetPassword_key, cleanup_duplicate_skills
from django.contrib.auth.hashers import make_password, check_password
from django.template.loader import get_template
from allauth.account.models import EmailAddress
from rest_framework_simplejwt.tokens import RefreshToken

from django.conf import settings
from .custom_signal import job_created, assist_created
from api.job_model.data_processing import DataPreprocessor
import resend
from scuibai.settings import RESEND_API_KEY
from django.core.mail import send_mail


from django.utils import timezone
from api.job_model.job_recommender import JobAppMatching

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

# Activate the resend with the api key
resend.api_key = settings.NEW_RESEND_API_KEY


def home(request):
    return render(request, "home.html")


# Get token or login View
class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer


""" AUTH """


# Register View
@swagger_auto_schema(
    method="post",
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
        # print(user.company)

        key, exp = VerifyEmail_key(user.id)

        template = get_template("register/verify_email.html")
        context = {"user": user, "otp": key, "expirary_date": exp}
        html = template.render(context)

        # subject = "Verify Your Email"
        # from_email = settings.DEFAULT_FROM_EMAIL
        # recipient_list = [user.email]

        # msg = EmailMultiAlternatives(subject, "Your email client does not support HTML.", from_email, recipient_list)
        # msg.attach_alternative(html, "text/html")
        params: resend.Emails.SendParams = {
            "from": "okpe@resend.dev",
            "to": [user.email],
            "subject": "VERIFY YOUR EMAIL",
            "html": html,
        }

        try:
            # msg.send()
            # r = resend.Emails.send(params)
            pass
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
                "data": {"key": key, "exp": exp},
            },
            status=status.HTTP_201_CREATED,
        )

    print(f"Serializer Error: {serialized_data.errors}, Data: {request.data}")

    return Response(serialized_data.errors, status=status.HTTP_400_BAD_REQUEST)


# Verify Email Here
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
        email = serializer.validated_data["email"]  # type: ignore
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

        if check_password(password, user.password):
            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),  # type: ignore
                    "user_id": user.id,  # type: ignore
                    "first_name": user.first_name,
                    "is_company": user.company,
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
    print(request.data)
    serialized_data = EmailVerifySerializer(data=request.data)
    if serialized_data.is_valid():
        # print(serialized_data.data)
        key = serialized_data.data["key"]  # type: ignore It works just pylance Type list errors
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
            return Response(
                {"detail": _("Email verified successfully.")}, status=status.HTTP_200_OK
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
    if data:

        key, uid = ResetPassword_key(email=data["email"])  # type: ignore pylance warning

        return Response(
            {"detail": {"uid": uid, "key": key}}, status=status.HTTP_201_CREATED
        )
    return Response(
        {"errors": "Something went wrong!"}, status=status.HTTP_400_BAD_REQUEST
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
            name="Authorization",
            in_=openapi.IN_HEADER,
            description="Bearer {token}",
            type=openapi.TYPE_STRING,
            required=True,
        ),
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
@permission_classes([IsAuthenticated])
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

    # Add other fields
    resume = None
    try:
        resume = Resume.objects.get(user=profile.user)
        profile_data["resume"] = resume.file.url
    except Resume.DoesNotExist:
        profile_data["resume"] = ""

    image = get_object_or_404(Image, user=profile.user)

    profile_data["email"] = profile.user.email
    profile_data["first_name"] = profile.user.first_name
    profile_data["last_name"] = profile.user.last_name if profile.user.last_name else ""
    profile_data["image"] = image.file.url if image else None
    profile_data["skills"] = profile.skills.values_list("name", flat=True)
    profile_data["categories"] = profile.categories.values_list("name", flat=True)

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

    # Add other fields
    resume = None
    try:
        resume = Resume.objects.get(user=profile.user)
        profile_data["resume"] = resume.file.url
    except Resume.DoesNotExist:
        profile_data["resume"] = ""

    image = get_object_or_404(Image, user=request.user)

    profile_data["email"] = profile.user.email
    profile_data["first_name"] = profile.user.first_name
    profile_data["last_name"] = profile.user.last_name if profile.user.last_name else ""
    profile_data["image"] = image.file.url if image else None
    profile_data["skills"] = profile.skills.values_list("name", flat=True)
    profile_data["categories"] = profile.categories.values_list("name", flat=True)
    profile_data["notifications"] = profile.notifications

    return Response({"data": profile_data}, status=status.HTTP_200_OK)


# Get all notifications
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
    ],
    request_body=ProfileSerializer,
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
def profile_update(request):
    user = request.user

    # Check if email is in field
    if "email" in request.data:
        request.data.pop("email")
    # Check if the profile exists
    try:
        profile = Profile.objects.get(user=user)
    except Profile.DoesNotExist:
        return Response(
            {"detail": "Profile does not exist"}, status=status.HTTP_404_NOT_FOUND
        )

    # Handle first_name and last_name
    if "first_name" in request.data:
        first_name = request.data.pop("first_name")
        profile.user.first_name = first_name
        profile.user.save()

    if "last_name" in request.data:
        last_name = request.data.pop("last_name")
        profile.user.last_name = last_name
        profile.user.save()

    # Handle skill updates
    if "skills" in request.data:
        new_skills = request.data.pop("skills")
        current_skills = set(profile.skills.values_list("name", flat=True))
        new_skills_set = set(new_skills)

        # Add new skills
        for skill_name in new_skills_set - current_skills:
            skill, created = UserSkills.objects.get_or_create(name=skill_name)
            profile.skills.add(skill)

        # Remove old skills
        for skill_name in current_skills - new_skills_set:
            skill = UserSkills.objects.get(name=skill_name)
            profile.skills.remove(skill)

    # Handle skill updates
    if "categories" in request.data:
        new_categories = request.data.pop("categories")
        current_categories = set(profile.categories.values_list("name", flat=True))
        new_categories_set = set(new_categories)

        # Add new skills
        for category_name in new_categories_set - current_categories:
            category, created = UserCategories.objects.get_or_create(name=category_name)
            profile.categories.add(category)

        # Remove old skills
        for category_name in current_categories - new_categories_set:
            category = UserCategories.objects.get(name=category_name)
            profile.categories.remove(category)

    if "image" in request.data:
        image = None
        try:
            # Attempt to retrieve the existing image
            image = Image.objects.get(user=profile.user)

            # Debugging: Check if the image file is a string or CloudinaryResource
            public_id = (
                image.file.public_id if hasattr(image.file, "public_id") else image.file
            )
            print(f"Existing image public_id: {public_id}")

            # Delete the existing image from Cloudinary
            cloudinary.uploader.destroy(public_id)

            # Upload the new image and update the file field
            image.file = cloudinary.uploader.upload(request.data["image"])["public_id"]  # type: ignore
            image.save()

            # Remove image from request data after processing
            request.data.pop("image")

        except Image.DoesNotExist:
            # If the image does not exist, upload the new image and create a new Image object
            file = uploader.upload(request.data["image"])["public_id"]  # type: ignore
            Image.objects.create(user=profile.user, file=file)

            # Remove image from request data after processing
            request.data.pop("image")

        except Exception as e:
            # Handle any other exceptions, such as issues with Cloudinary credentials
            print(f"Failed to delete or upload image: {e}")

    if "resume" in request.data:
        resume = None

        try:
            # Attempt to retrieve the existing resume
            resume = Resume.objects.get(user=profile.user)

            # Debugging: Check if the resume file is a string or Cloudinary Resource
            public_id = (
                resume.file.public_id
                if hasattr(resume.file, "public_id")
                else resume.file
            )
            print(f"Existing resume public_id: {public_id}")

            # Delete the existing resume from Cloudinary
            cloudinary.uploader.destroy(public_id)

            # Upload the new resume and update the file field
            resume.file = cloudinary.uploader.upload(request.data["resume"])["public_id"]  # type: ignore
            resume.save()

            # Remove resume from request data after processing
            request.data.pop("resume")

        except Resume.DoesNotExist:
            # If the resume does not exist, upload the new resume and create a new Resume object
            file = cloudinary.uploader.upload(request.data["resume"])["public_id"]  # type: ignore
            Resume.objects.create(user=profile.user, file=file)

            # Remove resume from request data after processing
            request.data.pop("resume")

        except Exception as e:
            # Handle any other exceptions, such as issues with Cloudinary credentials
            print(f"Failed to delete or upload resume: {e}")

    # Save edits
    profile.save()

    # Update profile with the remaining fields
    serialized_data = ProfileSerializer(profile, data=request.data, partial=True)
    # for attr, value in request.data.items():
    #     setattr(profile, attr, value)
    if serialized_data.is_valid():
        serialized_data.save()
        data = serialized_data.data
        print(User.objects.get(id=user.id).first_name)
        try:
            resume = Resume.objects.get(user=profile.user)
            data["resume"] = resume.file.url
        except Resume.DoesNotExist:
            data["resume"] = ""
        data["first_name"], data["last_name"] = (
            profile.user.first_name,
            profile.user.last_name,
        )
        data["image"] = Image.objects.get(user=user).file.url
        data["skills"] = set(profile.skills.values_list("name", flat=True))
        data["categories"] = set(profile.categories.values_list("name", flat=True))
        # curr_user = User.objects.get(id=user.id)

        return Response(
            {"_detail": "Succesful!", "data": data}, status=status.HTTP_200_OK
        )

    return Response(
        {"_detail": "An error occured!"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


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
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "first_name": openapi.Schema(
                type=openapi.TYPE_STRING, description="User's first name (optional)"
            ),
            "last_name": openapi.Schema(
                type=openapi.TYPE_STRING, description="User's last name (optional)"
            ),
            "skills": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_STRING),
                description="List of skills to update (optional)",
            ),
            "categories": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_STRING),
                description="List of categories to update (optional)",
            ),
            "image": openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_BINARY,
                description="Profile image file to upload (optional)",
            ),
            "resume": openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_BINARY,
                description="Resume file to upload (optional)",
            ),
            "years_of_experience": openapi.Schema(
                type=openapi.TYPE_NUMBER,
                description="Years of experience(optional)",
            ),
        },
        required=[],
    ),
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
@permission_classes([AllowAny])
def onboarding(request, user_id):
    # Check if the profile exists
    user = get_object_or_404(User, id=user_id)
    if not user:
        return Response(
            {"detail": "User does not exist"}, status=status.HTTP_404_NOT_FOUND
        )
    try:
        profile = Profile.objects.get(user=user)
    except Profile.DoesNotExist:
        return Response(
            {"detail": "Profile does not exist"}, status=status.HTTP_404_NOT_FOUND
        )

    # Handle user fields (first_name and last_name)
    if "first_name" in request.data:
        user.first_name = request.data.pop("first_name")

    if "last_name" in request.data:
        user.last_name = request.data.pop("last_name")

    # Handle skill updates
    if "skills" in request.data:
        new_skills = request.data.pop("skills")
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
            skill = UserSkills.objects.get(name=skill_name)
            profile.skills.remove(skill)

    # Handle skill updates
    if "categories" in request.data:
        new_categories = request.data.pop("categories")
        current_categories = set(profile.categories.values_list("name", flat=True))
        new_categories_set = set(new_categories)

        # Add new skills
        for category_name in new_categories_set - current_categories:
            category, created = UserCategories.objects.get_or_create(name=category_name)
            profile.categories.add(category)

        # Remove old skills
        for category_name in current_categories - new_categories_set:
            category = UserCategories.objects.get(name=category_name)
            profile.categories.remove(category)

    if "image" in request.data:
        image = get_object_or_404(Image, user=user)
        if image:
            image.file = cloudinary.uploader.upload(request.data["image"])["public_id"]  # type: ignore
            image.save()
            request.data.pop("image")
        else:
            file = cloudinary.uploader.upload(request.data["image"])["public_id"]  # type: ignore
            Image.objects.create(user=user, file=file)
            request.data.pop("image")

    if "resume" in request.data:
        resume = get_object_or_404(Resume, user=user)
        if resume:
            resume.file = cloudinary.uploader.upload(request.data["resume"])["public_id"]  # type: ignore
            resume.save()
            request.data.pop("resume")
        else:
            file = cloudinary.uploader.upload(request.data["resume"])["public_id"]  # type: ignore
            Resume.objects.create(user=user, file=file)
            request.data.pop("resume")

    # Update profile with the remaining fields
    serialized_data = ProfileSerializer(profile, data=request.data, partial=True)
    # for attr, value in request.data.items():
    #     setattr(profile, attr, value)
    if serialized_data.is_valid():
        serialized_data.save()

        return Response({"_detail": "Succesful!"}, status=status.HTTP_200_OK)

    return Response(
        {"_detail": "An error occured!"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


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
        required=["title", "description", "location", "employment_type"],
        properties={
            "title": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Job title",
            ),
            "description": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Detailed job description",
            ),
            "location": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Job location",
            ),
            "employment_type": openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=["Full-time", "Part-time", "Contract", "Remote"],
                description="Type of employment",
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

        # Get job skills
        job_skills = list(job_instance.skills.values_list("name", flat=True))

        # Prepare job data for the response
        data = {
            "job_id": job_instance.id,
            "owner_id": job_instance.owner.id,
            "company_name": job_instance.owner.first_name,
            "company_email": job_instance.owner.email,
            "skills": job_skills,
            "category": job_instance.categories,
            "title": job_instance.title,
            "description": job_instance.description,
            "location": job_instance.location,
            "employment_type": job_instance.employment_type,
            "max_salary": job_instance.max_salary,
            "min_salary": job_instance.min_salary,
            "currency_type": job_instance.currency_type,
        }

        # Send job creation signal (if applicable)
        # job_created.send(sender=Jobs, instance=job_instance)

        # Use the recommendation system to find suitable applicants
        matcher = JobAppMatching()

        job_data = matcher.load_job_from_db(job_instance.id)

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

        if user_profiles.empty:
            return Response(
                {
                    "detail": _("Job successfully posted!"),
                    "data": data,
                    "recommended_applicants": [],
                },
                status=status.HTTP_201_CREATED,
            )

        if user_profiles["skills"].str.strip().eq("").all():
            return Response(
                {
                    "detail": _("Job successfully posted!"),
                    "data": data,
                    "recommended_applicants": [],
                },
                status=status.HTTP_201_CREATED,
            )

        # Get top 5 matching applicants using the recommendation function
        recommended_users = matcher.recommend_users(job_data, user_profiles)

        # Prepare notification
        notification = {
            "id": str(uuid4()),
            "type": "job",
            "message": "You have been matched to a job",
            "datetime": timezone.now().isoformat(),
            "details": {
                "job_name": job_instance.title,
                "job_description": job_instance.description,
                "job_skills": job_skills,
            },
        }

        recommended_applicants_list = []

        for user_data in recommended_users:
            try:
                user_id = user_data["user_id"]
                profile = Profile.objects.get(user__id=user_id)

                # Ensure applicants are linked to the job
                applicant, created = Applicants.objects.get_or_create(job=job_instance)
                applicant.user.add(profile.user)

                # Collect recommended applicant info
                recommended_applicants_list.append(
                    {
                        "user_id": profile.user.id,
                        "user_name": profile.user.first_name,
                        "user_email": profile.user.email,
                        "User_bio": profile.bio,
                        "match_score": user_data["match_score"],
                        "years_of_experience": profile.years_of_experience,
                        "salary_range": user_data["salary_range"],
                        "location": profile.location,
                        "employment_choice": profile.employment_type,
                        "job_location_choice": profile.job_location,
                        "skills": list(profile.skills.values_list("name", flat=True)),
                    }
                )

                # Add notifications if not already present
                if not profile.notifications:
                    profile.notifications = []

                if notification not in profile.notifications:
                    profile.notifications.append(notification)
                    profile.save()

            except Profile.DoesNotExist:
                print(f"Profile not found for user ID {user_id}")
                continue

        # Add recommended applicants to response
        data["recommended_applicants"] = recommended_applicants_list

        return Response(
            {"detail": _("Job successfully posted!"), "data": data},
            status=status.HTTP_201_CREATED,
        )

    # Handle invalid data
    return Response(
        {"error": serialized_data.errors}, status=status.HTTP_400_BAD_REQUEST
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


@api_view(["GET"])
@permission_classes([AllowAny])
def jobs_all(request):
    jobs = Jobs.objects.all()
    serialized_jobs = JobSerializer(jobs, many=True)
    return Response(serialized_jobs.data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def jobs_user(request):
    jobs = Jobs.objects.filter(owner=request.user)
    data = []
    for job in jobs:
        applicants = Applicants.objects.filter(job=job)
        # print([User.objects.get(email=users.applicants) for users in applicants])
        print(applicant.user.values_list("first_name") for applicant in applicants)
        data.append(
            {
                "job": {
                    "job_id": job.id,
                    "description": job.description,
                    "location": job.location,
                    "role": job.categories,
                    "type": job.employment_type,
                    "skills": job.skills.values_list("name", flat=True),
                    "location": job.location,
                    "pay_range": f"{job.min_salary} - {job.max_salary}",
                    "experience": f"{job.min_experience} - {job.max_experience}",
                    "employment_type": job.get_employment_type_display(),
                    "created_at": job.created_at,
                },
                "applicants": [
                    {
                        "applicant_id": user.id,
                        "first_name": user.first_name,
                        "last_name": user.last_name if user.last_name else "",
                        "email": user.email,
                        # Profile fields
                        "phonenumber": user.profile.phonenumbers,
                        "image": user.profile.user.image.file.url,
                        "skills": user.profile.skills.values_list("name", flat=True),
                        "categories": user.profile.categories.values_list(
                            "name", flat=True
                        ),
                        "experience": user.profile.experience,
                    }
                    for applicant in applicants
                    for user in applicant.user.all()
                ],
            }
        )
    return Response(data, status=status.HTTP_200_OK)


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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def company(request):
    """Get the company's details"""
    owner = request.user
    try:
        company = CompanyProfile.objects.get(owner=owner)
        serializer = CompanySerializer(company)
        # Add the company name
        data = serializer.data.copy()
        data["company_name"] = company.owner.first_name
        return Response(data, status=status.HTTP_200_OK)
    except ObjectDoesNotExist:
        return Response(
            {"error": "CompanyProfile not found."}, status=status.HTTP_404_NOT_FOUND
        )


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def company_update(request):
    try:
        company_profile = CompanyProfile.objects.get(owner=request.user)
    except CompanyProfile.DoesNotExist:
        return Response(
            {"error": "Company profile not found."}, status=status.HTTP_404_NOT_FOUND
        )

    if request.user.id != company_profile.owner.id:
        return Response(
            {"error": "You do not have permission to edit this profile."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Edit company name
    if "company_name" in request.data:
        company_name = request.data.pop("company_name")
        company_profile.owner.first_name = company_name

    serializer = CompanySerializer(company_profile, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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


""" PAYMENT """


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def initialize_payment(request):
    user = get_object_or_404(User, id=request.user.id)

    if user.company:
        return Response(
            {"detail": _("Subscription does not support a company")},
            status=status.HTTP_403_FORBIDDEN,
        )

    print(request.data.get("amount"), type(request.data.get("amount")))
    amount = int(request.data.get("amount"))
    email = user.email
    plan = request.data.get("plan")

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    if "PLUS" == plan and amount < 100:
        return Response(
            {"detail": "Amount must be at least 100 for PLUS plan."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    elif "PRO" == plan and amount < 1000:
        return Response(
            {"detail": "Amount must be at least 1000 for PRO plan."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = {
        "email": email,
        "amount": amount * 100,  # Paystack expects the amount in kobo
        "callback_url": "https://www.scuib.com/payment/verify/",
    }

    response = requests.post(
        "https://api.paystack.co/transaction/initialize", headers=headers, json=data
    )
    response_data = response.json()

    if response.status_code == 200:
        return Response({"payment_url": response_data["data"]["authorization_url"]})
    else:
        return Response(
            {"error": response_data["message"]}, status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def verify_payment(request):
    reference = request.query_params.get("reference")
    plan = request.query_params.get("plan")

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
    }

    response = requests.get(
        f"https://api.paystack.co/transaction/verify/{reference}", headers=headers
    )
    response_data = response.json()

    print(response_data)
    if response_data["status"] == "success":
        amount = response_data["amount"] // 100
        Subscription.objects.create(user=request.user, amount=amount, plan=plan)
        return Response({"message": "Payment successful"})
    else:
        return Response(
            {"error": "Payment verification failed"}, status=status.HTTP_400_BAD_REQUEST
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
    company = serializer.validated_data["company"]

    try:
        user = User.objects.get(email=email)
        if user.auth_provider != "google":
            return Response(
                {"error": "Please login using your email and password"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
    except User.DoesNotExist:
        user_data = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "password": settings.SOCIAL_SECRET_KEY,
            "password2": settings.SOCIAL_SECRET_KEY,
            "auth_provider": "google",
            "company": company,
        }

        user_serializer = UserSerializer(data=user_data)
        if user_serializer.is_valid():
            user = user_serializer.save()
            user.email_verified = True
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
        }
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

    if user_profiles.empty:
        return Response(
            {
                "detail": "Job processed successfully!",
                "recommended_applicants": [],
            },
            status=status.HTTP_200_OK,
        )

    if user_profiles["skills"].str.strip().eq("").all():
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
    for user_data in recommended_users:
        try:
            user_id = user_data["user_id"]
            profile = Profile.objects.get(user_id=user_id)

            recommended_applicants_list.append(
                {
                    "user_id": profile.user.id,
                    "user_name": profile.user.first_name,
                    "user_email": profile.user.email,
                    "User_bio": profile.bio,
                    "match_score": user_data["match_score"],
                    "years_of_experience": profile.years_of_experience,
                    "salary_range": user_data["salary_range"],
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
            "detail": "Job processed successfully!",
            "recommended_applicants": recommended_applicants_list,
        },
        status=status.HTTP_200_OK,
    )
