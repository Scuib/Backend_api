import cloudinary.uploader
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
import cloudinary
from scuibai.settings import BASE_DIR, NEW_GOOGLE_CLIENT_ID
from google.oauth2 import id_token
from google.auth.transport import requests

from .models import (
    BoostJobs,
    JobPreference,
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
    Message,
    WalletTransaction,
    JobTweet,
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
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "password",
            "password2",
            "profile",
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

    def get_profile(self, user):
        if hasattr(user, "profile"):
            return MinimalProfileSerializer(user.profile).data
        elif hasattr(user, "company_profile"):
            return MinimalCompanyProfileSerializer(user.company_profile).data
        return None


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


class ProfileSerializer(serializers.ModelSerializer):
    skills = serializers.SlugRelatedField(
        many=True,
        slug_field="name",  # or whatever field identifies the skill
        queryset=UserSkills.objects.all(),
    )
    categories = serializers.SlugRelatedField(
        many=True,
        slug_field="name",  # same idea here
        queryset=UserCategories.objects.all(),
    )

    class Meta:
        model = Profile
        fields = "__all__"


class MinimalProfileSerializer(ModelSerializer):
    image = serializers.ImageField(use_url=True)

    class Meta:
        model = Profile
        fields = ["image"]


class MinimalCompanyProfileSerializer(ModelSerializer):
    image = serializers.ImageField(use_url=True)

    class Meta:
        model = CompanyProfile
        fields = ["image"]


class DisplayProfileSerializer(ModelSerializer):
    skills = UserSkillSerializer(many=True)
    image = serializers.SerializerMethodField()
    resume = serializers.SerializerMethodField()
    cover_letter = serializers.SerializerMethodField()
    categories = UserCategoriesSerializer(many=True)
    user = UserSerializer()

    class Meta:
        model = Profile
        fields = [
            "user",
            "bio",
            "location",
            "job_location",
            "employment_type",
            "min_salary",
            "max_salary",
            "years_of_experience",
            "phonenumbers",
            "currency",
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
    categories = serializers.SerializerMethodField()

    class Meta:
        model = Jobs
        fields = "__all__"

    def get_skills(self, obj):
        return list(obj.skills.values_list("name", flat=True))

    def get_categories(self, obj):
        return list(obj.categories.values_list("name", flat=True))


class CompanySerializer(ModelSerializer):
    profile = serializers.SerializerMethodField()

    class Meta:
        model = CompanyProfile
        fields = "__all__"


class CompanyProfileSerializer(ModelSerializer):

    class Meta:
        model = CompanyProfile
        fields = [
            "company_name",
            "address",
            "phone_number",
            "website",
            "description",
            "image",
        ]


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


class MessageSerializer(serializers.ModelSerializer):
    content = serializers.SerializerMethodField()
    sender = UserSerializer()
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id",
            "sender",
            "title",
            "content",
            "thread",
            "unlocked",
            "created_at",
            "replies",
        ]

    def get_content(self, obj):
        request = self.context.get("request")
        if obj.sender == request.user:
            return obj.content
        if obj.unlocked:
            return obj.content
        teaser = obj.content[:50]  # First 50 characters of the message
        return f"Preview: {teaser}... Pay ₦100 to view the full message."

    def get_replies(self, obj):
        replies = obj.replies.order_by("created_at")
        return MessageSerializer(replies, many=True, context=self.context).data


class SentMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "title", "content", "unlocked", "is_read", "created_at"]


class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = [
            "id",
            "amount",
            "type",
            "status",
            "description",
            "created_at",
        ]


class JobTweetSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobTweet
        fields = "__all__"


class BoostJobSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source="owner.id")
    job_skills = serializers.ListField(
        child=serializers.CharField(), write_only=True, required=False
    )
    job_categories = serializers.ListField(
        child=serializers.CharField(), write_only=True, required=False
    )

    class Meta:
        model = BoostJobs
        fields = [
            "id",
            "owner",
            "title",
            "description",
            "job_type",
            "job_nature",
            "location",
            "experience_level",
            "job_categories",
            "job_skills",
            "min_salary",
            "max_salary",
            "application_link",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        if attrs["min_salary"] > attrs["max_salary"]:
            raise serializers.ValidationError(
                "Minimum salary cannot be greater than maximum salary."
            )
        return attrs

    def validate_job_type(self, value):
        return value.upper()

    def create(self, validated_data):
        skill_names = validated_data.pop("job_skills", [])
        category_names = validated_data.pop("job_categories", [])

        job = BoostJobs.objects.create(**validated_data)

        # Attach skills
        for name in skill_names:
            normalized = name.strip().lower()
            skill, _ = JobSkills.objects.get_or_create(name=normalized)
            job.job_skills.add(skill)

        # Attach categories
        for name in category_names:
            normalized = name.strip().lower()
            category, _ = UserCategories.objects.get_or_create(name=normalized)
            job.job_categories.add(category)

        return job

    def update(self, instance, validated_data):
        skill_names = validated_data.pop("job_skills", None)
        category_names = validated_data.pop("job_categories", None)

        # Update scalar fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        # Update skills (replace, not append)
        if skill_names is not None:
            instance.job_skills.clear()

            for name in skill_names:
                normalized = name.strip().lower()

                skill, _ = JobSkills.objects.get_or_create(name=normalized)
                instance.job_skills.add(skill)

        # Update categories (replace, not append)
        if category_names is not None:
            instance.job_categories.clear()

            for name in category_names:
                normalized = name.strip().lower()

                category, _ = UserCategories.objects.get_or_create(name=normalized)
                instance.job_categories.add(category)

        return instance

    def get_skills(self, obj):
        return list(obj.job_skills.values_list("name", flat=True))

    def get_categories(self, obj):
        return list(obj.job_categories.values_list("name", flat=True))


class JobPreferenceSerializer(serializers.ModelSerializer):
    preferred_categories = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True
    )
    preferred_skills = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True
    )

    categories = serializers.SerializerMethodField(read_only=True)
    skills = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = JobPreference
        fields = [
            "preferred_job_types",
            "preferred_job_nature",
            "preferred_locations",
            "preferred_categories",
            "preferred_skills",
            "categories",
            "skills",
            "preferred_experience",
            "min_salary",
            "max_salary",
        ]

    def _set_categories_and_skills(self, instance, categories, skills):
        if categories is not None:
            instance.preferred_categories.clear()
            for name in categories:
                normalized = name.strip().lower()
                category, _ = UserCategories.objects.get_or_create(name=normalized)
                instance.preferred_categories.add(category)

        if skills is not None:
            instance.preferred_skills.clear()
            for name in skills:
                normalized = name.strip().lower()
                skill, _ = JobSkills.objects.get_or_create(name=normalized)
                instance.preferred_skills.add(skill)

    def create(self, validated_data):
        categories = validated_data.pop("preferred_categories", [])
        skills = validated_data.pop("preferred_skills", [])

        preference = JobPreference.objects.create(
            user=self.context["request"].user, **validated_data
        )

        self._set_categories_and_skills(preference, categories, skills)

        return preference

    def update(self, instance, validated_data):
        categories = validated_data.pop("preferred_categories", None)
        skills = validated_data.pop("preferred_skills", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        self._set_categories_and_skills(instance, categories, skills)

        return instance

    def get_categories(self, obj):
        return list(obj.preferred_categories.values_list("name", flat=True))

    def get_skills(self, obj):
        return list(obj.preferred_skills.values_list("name", flat=True))
