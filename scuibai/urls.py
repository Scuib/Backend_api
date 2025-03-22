from django.contrib import admin
from django.urls import path, include
from api import views

# drf imports

from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi


schema_view = get_schema_view(
    openapi.Info(
        title="Scuibai Backend API",
        default_version="v1",
        description="API documentation for your Scuibai detailing what endpoints are there and what data they require and in what format",
        contact=openapi.Contact(email="okpephillips.dev@gmail.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    path("api/auth/verify-email/", views.verify_email, name="verify_email"),
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
]
