from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenRefreshView



urlpatterns = [
    # path('', views.home, name='home'),
    path('auth/register/', views.register, name='register'),
    path('auth/resend-verify-email/', views.resend_verify_email, name='resend-verify-email'),
    path('auth/verify-email/', views.verify_email, name='verify_email'),
    path('auth/sign-in/', views.login, name='login'),
    path('logout/', views.logout, name="logout"),
    path('auth/refresh-token/', TokenRefreshView.as_view(), name="refresh-token"),
    path('password/reset/', views.reset_password, name='reset_password'),
    path('password/reset/confirm/<int:uid>/<str:key>/', views.confirm_reset_password, name='confirm_reset_password'),
    path('profile/', views.profile_detail, name='profile-detail'),
    path('profile/update/', views.profile_update, name='profile-update'),
    path('profile/delete/', views.profile_delete, name='delete-user'),
    path('upload/picture/', views.upload_image, name='upload-image'),
    path('upload/resume/', views.upload_resume, name='upload-resume'),
    path('upload/cover-letter/', views.upload_cover_letter, name='upload-cover-letter'),
    path('jobs/create/', views.job_create, name='job-create'),
    path('jobs/update/<int:job_id>/', views.job_update, name='job-update'),
    path('jobs/user/', views.user_jobs, name='user_jobs'),
    path('jobs/all/', views.all_jobs, name='all_jobs'),
    path('apply/<int:job_id>/', views.applicant, name='apply'),
    path('company/update/', views.company_update, name='company-update'),
    path('company/', views.company, name='company-profile'),
    path('assist/create/', views.assist_create, name='assist-create'),
    path('assist/update/', views.assist_update, name='assist-update'),
    path('waitlist/', views.waitlist, name='waitlist')
]