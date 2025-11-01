from django.urls import path
from . import views

urlpatterns = [
    # ===== Course URLs =====
    path('', views.CourseListView.as_view(), name='course-list'),
    path('<int:pk>/', views.CourseDetailView.as_view(), name='course-detail'),
    path('create/', views.CourseCreateView.as_view(), name='course-create'),
    path('<int:pk>/update/', views.CourseUpdateView.as_view(), name='course-update'),
    path('<int:pk>/delete/', views.CourseDeleteView.as_view(), name='course-delete'),
    path('<int:pk>/assign-mentor/', views.AssignMentorView.as_view(), name='assign-mentor'),
    
    # ✅ Download syllabus (moved up for better organization)
    path('<int:pk>/download-syllabus/', views.download_syllabus, name='download-syllabus'),
    
    # ===== Batch URLs =====
    path('batches/', views.BatchListView.as_view(), name='batch-list'),
    path('batches/<int:pk>/', views.BatchDetailView.as_view(), name='batch-detail'),
    path('batches/create/', views.BatchCreateView.as_view(), name='batch-create'),
    path('batches/<int:pk>/update/', views.BatchUpdateView.as_view(), name='batch-update'),
    path('batches/<int:pk>/delete/', views.BatchDeleteView.as_view(), name='batch-delete'),
    path('batches/<int:pk>/add-students/', views.AddStudentsToBatchView.as_view(), name='add-students'),
    path('batches/<int:batch_id>/students/', views.BatchStudentsView.as_view(), name='batch-students'),
    
    # ===== Mentor-Specific URLs =====
    path('mentor/batches/', views.MentorAssignedBatchesView.as_view(), name='mentor-batches'),
    path('mentor/batches/<int:pk>/', views.MentorBatchDetailView.as_view(), name='mentor-batch-detail'),
    
    # ===== Student-Specific URLs =====
    path('students/<int:student_id>/', views.StudentDetailView.as_view(), name='student-detail'),
    path('students/<int:student_id>/batches/', views.StudentBatchesView.as_view(), name='student-batches'),
    path('students/<int:student_id>/submissions/', views.StudentSubmissionsView.as_view(), name='student-submissions'),
]
