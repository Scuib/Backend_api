from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenRefreshView



urlpatterns = [
    # path('', views.home, name='home'),
    path('auth/register/', views.register, name='register'),
    path('auth/verify-email/', views.verify_email, name='verify_email'),
    path('auth/sign-in/', views.login, name='login'),
    path('logout/', views.logout, name="logout"),
    path('auth/refresh-token', TokenRefreshView.as_view(), name="refresh-token"),
    path('password/reset/', views.reset_password, name='reset_password'),
    path('password/reset/confirm/<int:uid>/<str:key>/', views.confirm_reset_password, name='confirm_reset_password'),
    path('profile/', views.profile_detail, name='profile-detail'),
    path('profile/update/', views.profile_update, name='profile-update'),
    path('profile/delete/', views.profile_delete, name='delete-user'),
    path('upload/picture/', views.upload_image, name='upload-image'),
    path('upload/resume/', views.upload_resume, name='upload-resume'),
    path('upload/cover-letter/', views.upload_cover_letter, name='upload-cover-letter'),
    path('jobs/create/', views.job_create, name='job-create'),
    path('jobs/update/', views.job_update, name='job-update')
]





