import cloudinary.uploader
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
import cloudinary
from scuibai.settings import BASE_DIR, NEW_GOOGLE_CLIENT_ID
from google.oauth2 import id_token
from google.auth.transport import requests

from .models import (
    JobSkills,
    User,
    Profile,
    UserCategories,
    UserSkills,
    EmailVerication_Keys,
    PasswordReset_keys,
    Jobs,
    Applicant,
    CompanyProfile,
)

from django.contrib.auth.hashers import make_password

from rest_framework.serializers import ModelSerializer

from rest_framework import serializers

# from pathlib import Path

# BASE_DIR = Path(__file__).resolve().parent.parent


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "password",
            "password2",
        ]

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("password2"):
            raise serializers.ValidationError("Passwords do not match.")
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")  # Remove confirm_password from validated data
        password = validated_data.pop(
            "password"
        )  # Remove confirm_password from validated data

        # validated_data['password'] = make_password(validated_data['password'])
        # Create User
        user = User.objects.create(**validated_data)
        user.set_password(password)
        # print(user)
        user.save()
        return user


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims
        token["username"] = user.username
        token["email"] = user.email

        return token


class UserSkillSerializer(ModelSerializer):
    class Meta:
        model = UserSkills
        fields = ["name"]


class UserCategoriesSerializer(ModelSerializer):
    class Meta:
        model = UserCategories
        fields = ["name"]


class ProfileSerializer(ModelSerializer):
    class Meta:
        model = Profile
        fields = "__all__"


class DisplayProfileSerializer(ModelSerializer):
    skills = UserSkillSerializer(many=True)
    image = serializers.SerializerMethodField()
    resume = serializers.SerializerMethodField()
    cover_letter = serializers.SerializerMethodField()
    categories = UserCategoriesSerializer(many=True)

    class Meta:
        model = Profile
        fields = [
            "bio",
            "location",
            "job_location",
            "employment_type",
            "min_salary",
            "max_salary",
            "years_of_experience",
            "phonenumbers",
            "github",
            "portfolio",
            "linkedin",
            "twitter",
            "skills",
            "image",
            "categories",
            "resume",
            "cover_letter",
            "notifications",
        ]

    def get_image(self, obj):
        return obj.image.url if obj.image else None

    def get_resume(self, obj):
        return obj.resume.url if obj.resume else None

    def get_cover_letter(self, obj):
        return obj.cover_letter.url if obj.cover_letter else None


class JobSkillSerializer(ModelSerializer):
    class Meta:
        model = JobSkills
        fields = ["name"]


class EmailVerifySerializer(ModelSerializer):
    class Meta:
        model = EmailVerication_Keys
        fields = ["key"]


# class ResetPasswordSerializer(ModelSerializer):
#     class Meta:
#         model = PasswordReset_keys
#         fields = ['user.email']


class ApplicantSerializer(ModelSerializer):
    class Meta:
        model = Applicant
        fields = "__all__"


class JobSerializer(serializers.ModelSerializer):
    skills = serializers.SerializerMethodField()

    class Meta:
        model = Jobs
        fields = "__all__"

    def get_skills(self, obj):
        return list(obj.skills.values_list("name", flat=True))


class CompanySerializer(ModelSerializer):
    class Meta:
        model = CompanyProfile
        fields = "__all__"


class CompanyProfileSerializer(ModelSerializer):

    class Meta:
        model = CompanyProfile
        fields = ["company_name", "address", "phone_number", "website", "description"]


class DisplayUsers(ModelSerializer):

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "company",
        ]


class GoogleAuthSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)

    def validate(self, attrs):
        token = attrs.get("token")
        try:
            id_info = id_token.verify_oauth2_token(
                token, requests.Request(), NEW_GOOGLE_CLIENT_ID
            )
            attrs["email"] = id_info.get("email")
            attrs["first_name"] = id_info.get("given_name", "")
            attrs["last_name"] = id_info.get("family_name", "")
            return attrs
        except ValueError as e:
            print("Token verification error:", e)
            raise serializers.ValidationError("Invalid Google token")
