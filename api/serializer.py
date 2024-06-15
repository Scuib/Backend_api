
import cloudinary.uploader
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
import cloudinary
from scuibai.settings import BASE_DIR
from .models import AllSkills, Image, Resume, User, Profile, UserSkills, EmailVerication_Keys, PasswordReset_keys, Jobs, Applicants

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
        fields = ['email', 'first_name', 'last_name', 'password', 'password2']

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('password2'):
            raise serializers.ValidationError("Passwords do not match.")
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')  # Remove confirm_password from validated data
        validated_data['password'] = make_password(validated_data['password'])
        # Create User
        user = User.objects.create(**validated_data)
        user.save()
        print(user)
        try:
            # Save Default Skill English
            skill = UserSkills.objects.create(user_id=user.id, name='english') # type: ignore
            skill.save()
            print(skill)
            # Save profile
            profile = Profile.objects.create(user=user, skills=skill)
            profile.save()
            print(profile)
            # Save Defualt Pictures
            file = cloudinary.uploader.upload(BASE_DIR / 'static/default.jpg')['public_id']
            image = Image.objects.create(user=user, file=file)
            image.save()
            print(image)

        except Exception as e:
            user.delete()  # Clean up if there's an error
            raise serializers.ValidationError(f"An error occurred: {e}")

        return user

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims
        token['username'] = user.username
        token['email'] = user.email
        

        return token


class ProfileSerializer(ModelSerializer):
    class Meta:
        model = Profile
        fields = ['bio', 'skills', 'location', 'job_location']

class ResumeSerializer(ModelSerializer):
    class Meta:
        model = Resume
        fields = ['file']

class CoverLetterSerializer(ModelSerializer):
    class Meta:
        model = Resume
        fields = ['file']

class ImageSerializer(ModelSerializer):
    class Meta:
        model = Resume
        fields = ['file']


class AllSkillSerializer(ModelSerializer):
    class Meta:
        model = AllSkills
        fields = ['name']

class UserSkillSerializer(ModelSerializer):
    class Meta:
        model = AllSkills
        fields = ['name']


class EmailVerifySerializer(ModelSerializer):
    class Meta:
        model = EmailVerication_Keys
        fields = ['key']

# class ResetPasswordSerializer(ModelSerializer):
#     class Meta:
#         model = PasswordReset_keys
#         fields = ['user.email']

class ApplicantSerializer(ModelSerializer):
    class Meta:
        model = Applicants
        fields = '__all__'

class JobSerializer(ModelSerializer):
    class Meta:
        model = Jobs
        fields = '__all__'
