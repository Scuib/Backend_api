from django.contrib import admin
from .models import User, Profile, EmailVerication_Keys, PasswordReset_keys, AllSkills, UserSkills
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

# Register your models here.
class UserAdminCustom(UserAdmin):
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {"classes": ("wide",), "fields": ("email", "first_name", "last_name", "password1", "password2"),},
        ),
    )
    list_display = ("email", "first_name", "last_name", "is_staff", "verified")
    search_fields = ("first_name", "last_name", "email", "verified")
    ordering = ("email",)
    readonly_fields = ['date_joined', 'last_login']

class ProfileAdmin(admin.ModelAdmin):
    list_display = ('get_user_id', 'get_user_first_name', 'location', 'job_location', 'get_skills')

    def get_user_id(self, obj):
        return obj.user.id
    get_user_id.short_description = 'User ID'

    def get_user_first_name(self, obj):
        return obj.user.first_name
    get_user_first_name.short_description = 'First Name'

    def get_skills(self, obj):
        return ", ".join([skill.name for skill in obj.skills.all()])
    get_skills.short_description = 'Skills'

class EmailVericationKeysAdmin(admin.ModelAdmin):
    list_display = ('get_user_id', 'get_user_first_name', 'key', 'exp')

    def get_user_id(self, obj):
        return obj.user.id
    get_user_id.short_description = 'User ID'

    def get_user_first_name(self, obj):
        return obj.user.first_name
    get_user_first_name.short_description = 'First Name'

class PasswordResetKeysAdmin(admin.ModelAdmin):
    list_display = ('get_user_id', 'get_user_first_name', 'key', 'exp')

    def get_user_id(self, obj):
        return obj.user.id
    get_user_id.short_description = 'User ID'

    def get_user_first_name(self, obj):
        return obj.user.first_name
    get_user_first_name.short_description = 'First Name'

class AllSkillsAdmin(admin.ModelAdmin):
    list_display = ('id', 'name',)

class UserSkillsAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'name')



admin.site.register(User, UserAdminCustom)
admin.site.register(Profile, ProfileAdmin)
admin.site.register(EmailVerication_Keys, EmailVericationKeysAdmin)
admin.site.register(PasswordReset_keys, PasswordResetKeysAdmin)
admin.site.register(AllSkills, AllSkillsAdmin)
admin.site.register(UserSkills, UserSkillsAdmin)
