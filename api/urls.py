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
    path("auth/login/", views.login, name="login"),
    path("auth/google/", views.google_auth, name="Googe-login"),
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
    path("job/user/", views.jobs_user, name="user_jobs"),
    path("job/all/", views.jobs_all, name="all_jobs"),
    path("job/delete/<int:job_id>", views.delete_job, name="job-delete"),
    path("company/profile/update/", views.company_update, name="company-update"),
    path("company/profile/", views.company, name="company-profile"),
    path("waitlist/", views.waitlist, name="waitlist"),
    path("notifications/", views.get_notifications, name="notifications"),
    path("users/", views.list_users, name="get all users"),
    path("profiles/", views.all_profiles, name="get all profiles"),
    path(
        "users/<int:user_id>/",
        views.delete_user_by_admin,
        name="Delete a user by admin",
    ),
    path(
        "create-job/",
        views.post_job_without_auth,
        name="Test job creation without login",
    ),
    path("company-status/", views.update_company_status, name="Set company status"),
    path("profile/headers/", views.profile_header, name="Get profile header"),
    path("contact/", views.contact_us, name="Contact us"),
    path("count/", views.count_users, name="count"),
    path("boost/", views.recommend_users_by_skills_and_location, name="boost"),
    path("wallet/fund/", views.fund_wallet, name="fund_wallet"),
    path("wallet/verify/<str:reference>/", views.verify_payment, name="verify_payment"),
    path("wallet/balance/", views.wallet_balance, name="wallet_balance"),
    path(
        "wallet/unlock-message/<int:message_id>/",
        views.unlock_message,
        name="unlock-message",
    ),
    path("messages/", views.list_messages, name="list-messages"),
    path("messages/send/", views.message_boost, name="send-messages"),
    path(
        "messages/delete/<int:message_id>/", views.delete_message, name="delete-message"
    ),
    path("wallet/transactions/", views.transaction_history, name="wallet-transactions"),
    path("fetch-twitter-jobs/", views.fetch_twitter_jobs, name="fetch-twitter-jobs"),
]
