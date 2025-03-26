import cloudinary.uploader
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
import cloudinary
from scuibai.settings import BASE_DIR, GOOGLE_CLIENT_ID
from google.oauth2 import id_token
from google.auth.transport import requests

from .models import (
    JobSkills,
    Image,
    Resume,
    User,
    Profile,
    UserCategories,
    UserSkills,
    Assists,
    EmailVerication_Keys,
    PasswordReset_keys,
    Jobs,
    Applicants,
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
            "company",
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
    # categories = UserCategoriesSerializer(many=True)

    class Meta:
        model = Profile
        fields = [
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
        ]


class ResumeSerializer(ModelSerializer):
    class Meta:
        model = Resume
        fields = ["file"]


class CoverLetterSerializer(ModelSerializer):
    class Meta:
        model = Resume
        fields = ["file"]


class ImageSerializer(ModelSerializer):
    class Meta:
        model = Resume
        fields = ["file"]


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
        model = Applicants
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
    company = serializers.BooleanField(default=False)

    def validate(self, attrs):
        token = attrs.get("token")
        try:
            id_info = id_token.verify_oauth2_token(
                token, requests.Request(), GOOGLE_CLIENT_ID
            )
            attrs["email"] = id_info.get("email")
            attrs["first_name"] = id_info.get("given_name", "")
            attrs["last_name"] = id_info.get("family_name", "")
            return attrs
        except ValueError:
            raise serializers.ValidationError("Invalid Google token")
