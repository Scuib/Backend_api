from django.http import JsonResponse
import cloudinary.uploader
from django.shortcuts import render, get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
import cloudinary
from .models import (CompanyProfile, Profile, User, EmailVerication_Keys, PasswordReset_keys, JobSkills, UserCategories,
                     UserSkills, AllSkills, Cover_Letter, Resume, Image, Jobs, Applicants)
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializer import (CompanySerializer, MyTokenObtainPairSerializer, UserSerializer, ProfileSerializer, EmailVerifySerializer, ApplicantSerializer,
                         LoginSerializer, ResumeSerializer, ImageSerializer, CoverLetterSerializer, JobSerializer, CompanySerializer)
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .tools import VerifyEmail_key, ResetPassword_key
from django.contrib.auth.hashers import make_password, check_password
from allauth.account.models import EmailAddress
from rest_framework_simplejwt.tokens import RefreshToken



def home(request):
    return render(request, 'home.html')


# Get token or login View
class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer


""" AUTH """
# Register View
@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serialized_data = UserSerializer(data=request.data)

    if serialized_data.is_valid():
        user = serialized_data.save()
        EmailAddress.objects.create(
            user=user,
            email=user.email # type: ignore
        )
        key, exp = VerifyEmail_key(user.id)

        return Response({'detail': {'name': user.first_name, 'key': key, 'expires': exp} }, status=status.HTTP_201_CREATED) # type: ignore
    return Response(serialized_data.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST', 'PUT'])
@permission_classes([IsAuthenticated])
def logout(request):
    try:
        refresh_token = request.data["refresh"]
        token = RefreshToken(refresh_token)
        token.blacklist()

        return Response(status=status.HTTP_205_RESET_CONTENT)
    except Exception as e:
        return Response(status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email'] # type: ignore
        password = serializer.validated_data['password'] # type: ignore


        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'Invalid email or password'}, status=status.HTTP_401_UNAUTHORIZED)
        
        if not EmailAddress.objects.get(email=email).verified:
                return Response({'error': 'Email is not verified '}, status=status.HTTP_401_UNAUTHORIZED)

        if check_password(password, user.password):
            # print(user.password)
            refresh = RefreshToken.for_user(user)
            # update_last_login(None, user)

            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token), # type: ignore
                'user_id': user.id, # type: ignore
                'first_name': user.first_name
            })
        else:
            print(user.password)
            return Response({'erro': 'Invalid email or password'}, status=status.HTTP_401_UNAUTHORIZED)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Verify Email Here
@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email(request):
    """
        This method verifies the use email exists by Matching the user Unique Key that was sent to the email
        request.data - ['key']
    """
    serialized_data = EmailVerifySerializer(data=request.data)
    if serialized_data.is_valid():
        print(serialized_data.data)
        key = serialized_data.data['key'] # type: ignore It works just pylance Type list errors
        try:
            unique_key = get_object_or_404(EmailVerication_Keys, key=key)
            if unique_key.exp <= timezone.now():
                return Response({'detail': _('Key has expired.')}, status=status.HTTP_404_NOT_FOUND)
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
            return Response({'detail': _('Email verified successfully.')}, status=status.HTTP_200_OK)
        except EmailVerication_Keys.DoesNotExist:
            return Response({'detail': _('Invalid verification key.')}, status=status.HTTP_404_NOT_FOUND)

    return Response(serialized_data.errors, status=status.HTTP_400_BAD_REQUEST)

# Reset password Here
@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    """
        Receives Email
        Check if Email is in database
        Send (uid, token) in a url
    """
    data = request.data
    if data:
        
        key, uid = ResetPassword_key(email=data['email']) # type: ignore pylance warning

        return Response({'detail': {'uid': uid, 'key': key}}, status=status.HTTP_201_CREATED)
    return Response({'errors': 'Something went wrong!'}, status=status.HTTP_400_BAD_REQUEST)

# Verify Email Here
@api_view(['POST'])
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
        reset_pwd_object = get_object_or_404(PasswordReset_keys, user=user, key=key)

        # Check if key has expired
        print(reset_pwd_object.exp)
        # print(timezone.now())
        if reset_pwd_object.exp <= timezone.now():
                return Response({'detail': _('Key has expired.')}, status=status.HTTP_404_NOT_FOUND)

        password = request.data.get('password')
        password2 = request.data.get('password2')
        # print(password)
        # print(password2)


        # Check if passwords match
        if password != password2:
            return Response({'detail': _('Passwords do not match.')}, status=status.HTTP_400_BAD_REQUEST)


        # Update the user's password
        print(f"Old password: {user.password}")
        user.set_password(password)
        user.save()
        print(f"New password: {user.password}")

        return Response({'detail': _('Password Successfully changed.')}, status=status.HTTP_201_CREATED)

    except User.DoesNotExist or PasswordReset_keys.DoesNotExist:
        return Response({'detail': _('User DoesNot Exist or Reset Password Key is Invalid')},
                        status=status.HTTP_404_NOT_FOUND)


""" PROFILE VIEWS """

# Profile Details of Authenticated User
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_detail(request):
    # Check if the profile exists
    try:
        profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    profile_data = {
        'name': f"{profile.user.first_name} {profile.user.last_name}",
        'bio': profile.bio,
        'skills': [skill.name for skill in profile.skills],
        'categories': [category.name for category in profile.categories],
        'location': profile.location,
        'job_location': profile.get_job_location_display(),
        'max_salary': profile.max_salary,
        'min_salary': profile.min_salary
    }

    return JsonResponse(profile_data, status=status.HTTP_200_OK)


# Profile Update of Authenticated User
@api_view(['POST', 'PUT'])
@permission_classes([IsAuthenticated])
def profile_update(request):
    # Check if the profile exists
    try:
        profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    # Update skills
    if 'skills' in request.data:
        user_skills = UserSkills.objects.filter(user_id=request.user.id).values_list('name', flat=True)
        new_skills = request.data.pop('skills')

        for skill in new_skills:
            if skill not in user_skills:
                user_skill, created = UserSkills.objects.get_or_create(user_id=request.user.id, name=skill)
                profile.objects.update(skills=user_skill)

    if 'categories' in request.data:
        categories = UserCategories.objects.filter(user=request.user.id).values_list('name', flat=True)
        new_categories = request.data.pop('categories')

        for category in new_categories:
            if category not in categories:
                user_category, created = UserCategories.objects.get_or_create(user_id=request.user.id, name=category)
                profile.objects.update(category=user_category)

    # Update profile with the remaining fields
    for attr, value in request.data.items():
        setattr(profile, attr, value)
    profile.save()

    return Response(ProfileSerializer(profile).data, status=status.HTTP_200_OK)


# Delete Authenticated User
@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def profile_delete(request):
    try:
        # Fetch the profile of the authenticated user
        profile = Profile.objects.get(user=request.user)

        # Delete the profile
        profile.delete()

        # Optionally delete the user account
        user = request.user
        user.delete()

        return Response({"detail": "User and profile deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
    except Profile.DoesNotExist:
        return Response({"detail": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


""" CLOUDINARY FILES VIEWS """

# Upload Resume
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_resume(request):
    serialized_data = ResumeSerializer(data=request.data)
    
    if serialized_data.is_valid():
        try:
            # Check if resume exists for the user
            resume = Resume.objects.get(user=request.user)
            # Update the file field
            resume.file = cloudinary.uploader.upload(serialized_data.validated_data['file'])['public_id'] # type: ignore
            resume.save()
            return Response("Resume updated successfully")
        except Resume.DoesNotExist:
            # Create a new resume if it does not exist
            file= cloudinary.uploader.upload(serialized_data.validated_data['file'])['public_id'] # type: ignore
            resume = Resume.objects.create(user=request.user, file=file)
            resume.save()
            return Response("Resume uploaded successfully")
    else:
        return Response(serialized_data.errors, status=400)


# Upload Cover letter
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_cover_letter(request):
    serialized_data = CoverLetterSerializer(data=request.data)
    
    if serialized_data.is_valid():
        try:
            # Check if cover letter exists for the user
            cover_letter = Cover_Letter.objects.get(user=request.user)
            # Update the file field
            cover_letter.file = cloudinary.uploader.upload(serialized_data.validated_data['file'])['public_id'] # type: ignore
            cover_letter.save()
            return Response("Resume updated successfully")
        except Cover_Letter.DoesNotExist:
            # Create a new resume if it does not exist
            file= cloudinary.uploader.upload(serialized_data.validated_data['file'])['public_id'] # type: ignore
            cover_letter = Cover_Letter.objects.create(user=request.user, file=file)
            cover_letter.save()
            return Response("Resume uploaded successfully")
    else:
        return Response(serialized_data.errors, status=400)


# Upload Image
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_image(request):
    try:
        image = Image.objects.get(user=request.user)
    except Exception:
        return Response("Image does not exist", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    serialized_data = ImageSerializer(data=request.data)

    if serialized_data.is_valid():
        file = cloudinary.uploader.upload(serialized_data.validated_data['file'])['public_id'] # type: ignore
        image.file=file

        image.save()

        print(image)
        return Response({'detail': _('Successfully updated!')},
                        status=status.HTTP_404_NOT_FOUND)

    return Response({'detail': _('Data Not Valid')},
                        status=status.HTTP_404_NOT_FOUND)


""" JOB VIEWS """

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def job_create(request):
    request.data['owner'] = request.user.id  # Ensure user is set correctly

    new_skills = request.data.pop('skills', [])
    # print(new_skills)

    serialized_data = JobSerializer(data=request.data)
    print(serialized_data.is_valid())

    if serialized_data.is_valid():
        serialized_data.save()

        # Create JobSkills relationships
        job = Jobs.objects.get(id=serialized_data.data['id'])
    
        for skill in new_skills:
            job_skill, created = JobSkills.objects.get_or_create(job=job, name=skill)
            job_skill.save()

        return Response({'detail': _("Job Successfully posted!")}, status=status.HTTP_201_CREATED)
    
    return Response(serialized_data.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST', 'PUT'])
@permission_classes([IsAuthenticated])
def job_update(request):
    try:
        job = Jobs.objects.get(user=request.user)
    except Jobs.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    # Update profile with the remaining fields
    for attr, value in request.data.items():
        setattr(job, attr, value)
    job.save()

    # Update skills
    if 'skills' in request.data:
        job_skills = JobSkills.objects.filter(job=job).values_list('name', flat=True)
        new_skills = request.data.pop('skills')

        for skill in new_skills:
            if skill not in job_skills:
                JobSkills.objects.get_or_create(job=job, name=skill)

    return Response(ProfileSerializer(job).data, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_jobs(request):
    user = request.user
    jobs = Jobs.objects.filter(owner=user)
    skills = JobSkills.objects.filter()
    job_list = []
    for job in jobs:
        skills = [skill.name for skill in skills] # job_skills is the related_name in JobSkills
        job_data = {
            'id': job.id,
            'title': job.title,
            'description': job.description,
            'location': job.location,
            'max_salary': job.max_salary,
            'min_salary': job.min_salary,
            'currency_type': job.currency_type,
            'employment_type': job.employment_type,
            'experience_level': job.experience_level,
            'skills': skills,
        }
        job_list.append(job_data)
    return Response(job_list)


@api_view(['GET'])
@permission_classes([AllowAny])
def all_jobs(request):
    jobs = Jobs.objects.all()
    job_list = []
    for job in jobs:
        skills = [skill.name for skill in job.job_skills.all()]
        job_data = {
            'id': job.id,
            'title': job.title,
            'description': job.description,
            'location': job.location,
            'max_salary': job.max_salary,
            'min_salary': job.min_salary,
            'currency_type': job.currency_type,
            'employment_type': job.employment_type,
            'experience_level': job.experience_level,
            'skills': skills,
        }
        job_list.append(job_data)
    return Response(job_list)


""" Applicants  """
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def applicant(request, job_id):
    try:
        job = Jobs.objects.get(id=job_id)
    except Jobs.DoesNotExist as e:
        return Response({'error': 'Job not found.'}, status=status.HTTP_404_NOT_FOUND)
    data = request.data.copy()
    data['job'] = job.id

    serialized_data = ApplicantSerializer(data=data)
    if serialized_data.is_valid():
        serialized_data.save()

        response = {
            "job_id": serialized_data.job.id,
            "job_title": serialized_data.job.title,
            "applicant_id": serialized_data.applicant.id,
            "applicant_name": serialized_data.applicant.first_name,
        }
        return Response(response, status=status.HTTP_201_CREATED)
    else:
        return Response(serialized_data.errors, status=status.HTTP_400_BAD_REQUEST)

""" Comapny """
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def company(request, company_id):
    """get the company's details """
    owner = User.objects.get(id=company_id)
    comapany = CompanyProfile.objects.get(owner=owner)

    return Response(CompanySerializer(company).data, status=status.HTTP_200_OK)

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def company_update(request, company_id):
    try:
        company_profile = CompanyProfile.objects.get(owner_id=company_id)
    except CompanyProfile.DoesNotExist:
        return Response({'error': 'Company profile not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.user.id != company_profile.owner.id:
        return Response({'error': 'You do not have permission to edit this profile.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = CompanySerializer(company_profile, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
