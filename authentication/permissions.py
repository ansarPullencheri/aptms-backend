from rest_framework import permissions

class IsAdmin(permissions.BasePermission):
    """Custom permission to only allow admins to access."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'

class IsMentor(permissions.BasePermission):
    """Custom permission to only allow mentors to access."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'mentor'

class IsStudent(permissions.BasePermission):
    """Custom permission to only allow students to access."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'student'

class IsAdminOrMentor(permissions.BasePermission):
    """Custom permission to allow admins and mentors."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['admin', 'mentor']
