
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('dj_rest_auth.urls')),
    path('api/auth/registration/', include('dj_rest_auth.registration.urls')),
    path('api/', include('api.urls')),
    # path('dj-rest-auth/registration/account-confirm-email/<str:key>/', email_confirmation),
    # path('reset/password/confirm/<int:uid>/<str:token>', reset_password_confirm, name="PasswordReset_keys_confirm"),
    # path('dj-rest-auth/google/', GoogleLogin.as_view(), name='google_login'),
]
