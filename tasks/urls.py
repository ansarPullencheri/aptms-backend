from django.urls import path
from . import views

urlpatterns = [
    # Task URLs
    path('', views.TaskListView.as_view(), name='task-list'),
    path('<int:pk>/', views.TaskDetailView.as_view(), name='task-detail'),
    path('create/', views.TaskCreateView.as_view(), name='task-create'),
    path('<int:pk>/update/', views.TaskUpdateView.as_view(), name='task-update'),
    path('<int:pk>/delete/', views.TaskDeleteView.as_view(), name='task-delete'),
    path('assigned/', views.AssignedTasksView.as_view(), name='assigned-tasks'),
    path('mentor/create/', views.MentorCreateTaskView.as_view(), name='mentor-create-task'),
    path('mentor/tasks/', views.MentorTasksListView.as_view(), name='mentor-tasks-list'),
    path('student/submit/', views.StudentSubmitTaskView.as_view(), name='student-submit-task'),
    path('student/task/<int:task_id>/', views.StudentTaskDetailView.as_view(), name='student-task-detail'),
    
    # Submission URLs
    path('<int:task_id>/submit/', views.TaskSubmissionView.as_view(), name='task-submit'),
    path('submissions/', views.SubmissionListView.as_view(), name='submission-list'),
    path('submissions/<int:pk>/', views.SubmissionDetailView.as_view(), name='submission-detail'),
    path('submissions/<int:pk>/grade/', views.GradeSubmissionView.as_view(), name='grade-submission'),
    
    # Mentor-specific task URLs
    path('mentor/batch/<int:batch_id>/tasks/', views.MentorBatchTasksView.as_view(), name='mentor-batch-tasks'),
    path('mentor/batch/<int:batch_id>/submissions/', views.BatchTaskSubmissionsView.as_view(), name='batch-submissions'),
    path('student/<int:student_id>/submitted/', views.StudentSubmittedTasksView.as_view(), name='student-submitted-tasks'),
    path('student/<int:student_id>/assigned/', views.StudentAssignedTasksView.as_view(), name='student-assigned-tasks'),
]
