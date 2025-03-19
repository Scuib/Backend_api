from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenRefreshView


urlpatterns = [
    # path('', views.home, name='home'),
    path("auth/register/", views.register, name="register"),
    path(
        "auth/resend-verify-email/",
        views.resend_verify_email,
        name="resend-verify-email",
    ),
    path("auth/sign-in/", views.login, name="login"),
    path("delete/", views.delete_user, name="delete-user"),
    path("logout/", views.logout, name="logout"),
    path("auth/refresh-token/", TokenRefreshView.as_view(), name="refresh-token"),
    path("password/reset/", views.reset_password, name="reset_password"),
    path(
        "password/reset/confirm/<int:uid>/<str:key>/",
        views.confirm_reset_password,
        name="confirm_reset_password",
    ),
    path("profile/", views.profile_detail, name="profile-detail"),
    path(
        "profile/<int:user_id>/", views.profile_detail_by_id, name="profile-detail-id"
    ),
    path("profile/update/", views.profile_update, name="profile-update"),
    path("onboarding/<int:user_id>/", views.onboarding, name="onboarding"),
    path("profile/delete/", views.profile_delete, name="delete-user"),
    path("job/create/", views.job_create, name="job-create"),
    path("job/update/<int:job_id>/", views.job_update, name="job-update"),
    path(
        "job/applicants/new/<int:job_id>/",
        views.get_new_applicants,
        name="get-new-applicants",
    ),
    path("job/user/", views.jobs_user, name="user_jobs"),
    path("job/all/", views.jobs_all, name="all_jobs"),
    path("job/delete/<int:job_id>", views.delete_job, name="job-delete"),
    path("company/update/", views.company_update, name="company-update"),
    path("company/", views.company, name="company-profile"),
    path("assist/", views.assist_for_you, name="assist-for-you"),
    path("assist/create/", views.assist_create, name="assist-create"),
    path("assist/update/", views.assist_update, name="assist-update"),
    path("assist/delete/<assist_id>", views.delete_assist, name="assist-delete"),
    path("waitlist/", views.waitlist, name="waitlist"),
    path("payment/initialize/", views.initialize_payment, name="initialize_payment"),
    path("payment/verify/", views.verify_payment, name="verify_payment"),
    path("notifications/", views.get_notifications, name="notifications"),
    path("users/", views.list_users, name="get all users"),
    path("profiles/", views.all_profiles, name="get all profiles"),
]
