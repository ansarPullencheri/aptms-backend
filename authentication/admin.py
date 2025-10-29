from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, StudentProfile, MentorProfile

class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'is_approved', 'is_staff']
    list_filter = ['role', 'is_approved', 'is_staff']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('role', 'phone', 'profile_picture', 'is_approved')}),
    )

admin.site.register(User, UserAdmin)
admin.site.register(StudentProfile)
admin.site.register(MentorProfile)
