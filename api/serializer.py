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
            "boost_id",
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


class JobPreferenceSerializer(serializers.ModelSerializer):
    preferred_categories = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True
    )

    preferred_categories_display = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = JobPreference
        fields = [
            "preferred_job_types",
            "preferred_job_nature",
            "preferred_locations",
            "preferred_categories",
            "preferred_categories_display",
            "preferred_experience",
            "min_salary",
            "max_salary",
        ]

    def get_preferred_categories_display(self, obj):
        return list(obj.preferred_categories.values_list("name", flat=True))

    def create(self, validated_data):
        category_names = validated_data.pop("preferred_categories", [])

        instance = JobPreference.objects.create(**validated_data)

        if category_names:
            categories = UserCategories.objects.filter(name__in=category_names)

            if categories.count() != len(category_names):
                existing = set(categories.values_list("name", flat=True))
                missing = set(category_names) - existing
                raise serializers.ValidationError(
                    {
                        "preferred_categories": f"Invalid categories: {', '.join(missing)}"
                    }
                )

            instance.preferred_categories.set(categories)

        return instance

    def update(self, instance, validated_data):
        category_names = validated_data.pop("preferred_categories", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if category_names is not None:
            categories = UserCategories.objects.filter(name__in=category_names)

            if categories.count() != len(category_names):
                existing = set(categories.values_list("name", flat=True))
                missing = set(category_names) - existing
                raise serializers.ValidationError(
                    {
                        "preferred_categories": f"Invalid categories: {', '.join(missing)}"
                    }
                )

            instance.preferred_categories.set(categories)

        return instance
