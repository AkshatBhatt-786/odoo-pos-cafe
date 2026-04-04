from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'phone', 'is_active')
    list_filter = ('role', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('POS Info', {'fields': ('role', 'phone', 'profile_picture', 'is_active_session', 'current_session_id')}),
    )

admin.site.register(User, CustomUserAdmin)