from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import AllSkills, User, Profile, UserSkills, EmailVerication_Keys, PasswordReset_keys

from django.contrib.auth.hashers import make_password

from rest_framework.serializers import ModelSerializer

from rest_framework import serializers


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
        # Save Default Skill English
        skill = UserSkills.objects.create(user_id=user.id, name='english') # type: ignore
        skill.save()
        # Save profile
        profile = Profile.objects.create(user=user, skills=skill)
        profile.save()

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
        fields = ['user', 'bio', 'resume_url', 'image_url', 'skills', 'location', 'job_location', 'cover_letter_url']


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