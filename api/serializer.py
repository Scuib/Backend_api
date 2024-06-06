from attr import fields
from questionary import password
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
        user = User.objects.create(**validated_data)
        return user

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims
        token['username'] = user.username
        token['email'] = user.email
        

        return token


class profileSerializer(ModelSerializer):
    class Meta:
        model = Profile
        fields = '__all__'


class AllSkillsSerializer(ModelSerializer):
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