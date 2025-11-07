from django.urls import path
from . import views

urlpatterns = [
    # ===== Task URLs =====
    path('', views.TaskListView.as_view(), name='task-list'),
    path('<int:pk>/', views.TaskDetailView.as_view(), name='task-detail'),
    path('create/', views.TaskCreateView.as_view(), name='task-create'),
    path('<int:pk>/update/', views.TaskUpdateView.as_view(), name='task-update'),
    path('<int:pk>/delete/', views.TaskDeleteView.as_view(), name='task-delete'),
    path('assigned/', views.AssignedTasksView.as_view(), name='assigned-tasks'),
    
    # ===== Student Task URLs =====
    path('student/submit/', views.StudentSubmitTaskView.as_view(), name='student-submit-task'),
    path('student/task/<int:task_id>/', views.StudentTaskDetailView.as_view(), name='student-task-detail'),
    
    # ===== Submission URLs =====
    path('<int:task_id>/submit/', views.TaskSubmissionView.as_view(), name='task-submit'),
    path('submissions/', views.SubmissionListView.as_view(), name='submission-list'),
    path('submissions/<int:pk>/', views.SubmissionDetailView.as_view(), name='submission-detail'),
    path('submissions/<int:pk>/grade/', views.GradeSubmissionView.as_view(), name='grade-submission'),
    
    # ===== Mentor Task Creation & Management =====
    path('mentor/create/', views.MentorCreateTaskView.as_view(), name='mentor-create-task'),
    path('mentor/tasks/', views.MentorTasksListView.as_view(), name='mentor-tasks-list'),
    path('mentor/batch/<int:batch_id>/tasks/', views.MentorBatchTasksView.as_view(), name='mentor-batch-tasks'),
    
    # ===== Mentor Submission Views =====
    path('mentor/submissions/pending/', views.MentorPendingSubmissionsView.as_view(), name='mentor-pending-submissions'),
    path('mentor/submissions/<int:submission_id>/', views.MentorSubmissionDetailView.as_view(), name='mentor-submission-detail'),
    path('mentor/submissions/<int:submission_id>/grade/', views.MentorGradeSubmissionView.as_view(), name='mentor-grade-submission'),
    path('mentor/submissions/graded/', views.MentorGradedSubmissionsView.as_view(), name='mentor-graded-submissions'),
    
    # ===== Mentor Batch Submissions =====
    path('mentor/batch/<int:batch_id>/submissions/', views.BatchTaskSubmissionsView.as_view(), name='batch-submissions'),
    
    # ===== Student View for Mentors =====
    path('student/<int:student_id>/submitted/', views.StudentSubmittedTasksView.as_view(), name='student-submitted-tasks'),
    path('student/<int:student_id>/assigned/', views.StudentAssignedTasksView.as_view(), name='student-assigned-tasks'),
    
    # ===== Weekly Progress Review URLs =====
    # GET: Load existing review | POST: Save review (same endpoint)
    path('mentor/weekly-review/<int:batch_id>/<int:student_id>/<int:week_number>/', 
         views.MentorWeeklyReviewView.as_view(), 
         name='mentor-weekly-review'),
    
    # Get students in batch for weekly review dropdown
    path('mentor/batch/<int:batch_id>/students/', 
         views.BatchStudentsWeeklyListView.as_view(), 
         name='batch-students-weekly'),
    path('student/weekly-review/<int:week_number>/', 
     views.StudentWeeklyReviewView.as_view(), 
     name='student-weekly-review'),
    path('mentor/all-reviews/', 
     views.MentorAllReviewsView.as_view(), 
     name='mentor-all-reviews'), 
     
]
