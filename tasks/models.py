from django.db import models
from authentication.models import User
from courses.models import Course, Batch
from django.utils import timezone


# class Task(models.Model):
#     STATUS_CHOICES = [
#         ('pending', 'Pending'),
#         ('in_progress', 'In Progress'),
#         ('completed', 'Completed'),
#         ('overdue', 'Overdue'),
#     ]
    
#     TASK_TYPE_CHOICES = [
#         ('batch', 'Batch Specific'),
#         ('course', 'Course Wide'),
#     ]
    
#     title = models.CharField(max_length=200)
#     description = models.TextField()
#     course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='tasks')
#     batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='tasks', 
#                              blank=True, null=True)
#     task_type = models.CharField(max_length=10, choices=TASK_TYPE_CHOICES, default='batch')
#     assigned_to = models.ManyToManyField(User, related_name='assigned_tasks', blank=True)
#     created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
#                                   related_name='tasks_created')
#     due_date = models.DateTimeField()
#     max_marks = models.IntegerField(default=100)
#     attachment = models.FileField(upload_to='task_attachments/', blank=True, null=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     def __str__(self):
#         if self.task_type == 'course':
#             return f"{self.title} (Course: {self.course.name})"
#         return f"{self.title} (Batch: {self.batch.name if self.batch else 'N/A'})"
    
#     class Meta:
#         ordering = ['-created_at']

# class Task(models.Model):
#     course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='tasks')
#     batch = models.ForeignKey('courses.Batch', on_delete=models.CASCADE, related_name='tasks', null=True, blank=True)
#     title = models.CharField(max_length=200)
#     description = models.TextField()
#     due_date = models.DateTimeField()
#     max_marks = models.IntegerField(default=100)
#     created_by = models.ForeignKey('authentication.User', on_delete=models.SET_NULL, null=True, related_name='created_tasks')
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#     assigned_to = models.ManyToManyField('authentication.User', related_name='assigned_tasks', blank=True)
#     task_type = models.CharField(max_length=20, choices=[('course', 'Course-wide'), ('batch', 'Batch-specific')], default='batch')
#     task_order = models.IntegerField(default=0) 
    
#     class Meta:
#         ordering = ['task_order', 'created_at']  
    
#     def __str__(self):
#         return f"{self.title} - {self.course.name}"


class Task(models.Model):
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='tasks')
    batch = models.ForeignKey('courses.Batch', on_delete=models.CASCADE, related_name='tasks', null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    due_date = models.DateTimeField()
    max_marks = models.IntegerField(default=100)
    created_by = models.ForeignKey('authentication.User', on_delete=models.SET_NULL, null=True, related_name='created_tasks')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    assigned_to = models.ManyToManyField('authentication.User', related_name='assigned_tasks', blank=True)
    task_type = models.CharField(max_length=20, choices=[('course', 'Course-wide'), ('batch', 'Batch-specific')], default='batch')
    task_order = models.IntegerField(default=0)
    
    # ✅ Weekly scheduling fields
    week_number = models.IntegerField(default=1, help_text="Week number in the course (1, 2, 3, etc.)")
    release_date = models.DateTimeField(null=True, blank=True, help_text="Date when task becomes available to students")
    is_scheduled = models.BooleanField(default=False, help_text="Is this a scheduled task?")
    
    class Meta:
        ordering = ['week_number', 'task_order', 'created_at']
    
    def __str__(self):
        return f"Week {self.week_number} - {self.title}"
    
    def is_available(self):
        """Check if task is available based on release date"""
        if not self.is_scheduled:
            return True
        if self.release_date:
            return timezone.now() >= self.release_date
        return True
class TaskSubmission(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_submissions')
    submission_file = models.FileField(upload_to='task_submissions/', blank=True, null=True)
    submission_text = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    marks_obtained = models.IntegerField(blank=True, null=True)
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='graded_submissions')
    graded_at = models.DateTimeField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.student.username} - {self.task.title}"
    
    class Meta:
        unique_together = ['task', 'student']
        ordering = ['-submitted_at']
