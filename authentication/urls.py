from django.urls import path
from .views import (
    StudentRegistrationView, 
    LoginView, 
    PendingStudentsView, 
    ApproveStudentView,
    UserListView,
    MentorListView,
    StudentListView,
    CreateMentorView,
    UserDetailView,
    AdminResetPasswordView,
    AdminGeneratePasswordView,
)
from .student_views import (
    StudentDashboardView,
    StudentTasksView,
    StudentPendingTasksView,
    StudentSubmittedTasksView,
    StudentAcademicProgressView,
    StudentTaskDetailView,
    StudentSubmitTaskView,
)




from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from .views import ExportStudentsToGoogleSheetView


from .views import ForgotPasswordView, ResetPasswordView
urlpatterns = [
    # ===== Authentication URLs =====
    path('register/', StudentRegistrationView.as_view(), name='student-register'),
    path('login/', LoginView.as_view(), name='login'),
    
    
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    # path('reset-password/<uidb64>/<token>/', ResetPasswordView.as_view(), name='reset-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    
    # ===== Admin User Management URLs =====
    path('pending-students/', PendingStudentsView.as_view(), name='pending-students'),
    path('approve-student/<int:user_id>/', ApproveStudentView.as_view(), name='approve-student'),
    path('users/', UserListView.as_view(), name='user-list'),
    path('users/<int:pk>/', UserDetailView.as_view(), name='user-detail'),
    
    # ===== Mentor Management URLs =====
    path('mentors/', MentorListView.as_view(), name='mentor-list'),
    path('create-mentor/', CreateMentorView.as_view(), name='create-mentor'),
    
    # ===== Student Management URLs =====
    path('students/', StudentListView.as_view(), name='student-list'),
    
    # ===== Student Dashboard & Tasks URLs =====
    path('student/dashboard/', StudentDashboardView.as_view(), name='student-dashboard'),
    path('student/tasks/', StudentTasksView.as_view(), name='student-tasks'),
    path('student/tasks/pending/', StudentPendingTasksView.as_view(), name='student-pending-tasks'),
    path('student/tasks/<int:pk>/', StudentTaskDetailView.as_view(), name='student-task-detail'),
    path('student/tasks/submit/', StudentSubmitTaskView.as_view(), name='student-submit-task'),
    path('student/submissions/', StudentSubmittedTasksView.as_view(), name='student-submissions'),
    path('student/progress/', StudentAcademicProgressView.as_view(), name='student-progress'),
    
    # ===== Admin Password Management URLs =====
    path('admin/reset-password/', AdminResetPasswordView.as_view(), name='admin-reset-password'),
    path('admin/generate-password/', AdminGeneratePasswordView.as_view(), name='admin-generate-password'),
    
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    path('export-to-sheet/', ExportStudentsToGoogleSheetView.as_view(), name='export_to_sheet'),
]
