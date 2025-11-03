from django.db import models
from django.utils import timezone
from authentication.models import User
from courses.models import Course, Batch


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
    # ✅ Status choices for submissions
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('graded', 'Graded'),
    ]
    
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_submissions')
    submission_file = models.FileField(upload_to='task_submissions/', blank=True, null=True)
    submission_text = models.TextField(blank=True, null=True)  # ✅ Changed to null=True
    submitted_at = models.DateTimeField(auto_now_add=True)
    marks_obtained = models.FloatField(blank=True, null=True)  # ✅ Changed to FloatField for decimal marks
    feedback = models.TextField(blank=True, null=True)  # ✅ Added null=True
    graded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='graded_submissions')
    graded_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(  # ✅ ADDED THIS FIELD
        max_length=20, 
        default='submitted', 
        choices=STATUS_CHOICES,
        help_text="Current status of the submission"
    )
    
    def __str__(self):
        return f"{self.student.username} - {self.task.title}"
    
    class Meta:
        unique_together = ['task', 'student']
        ordering = ['-submitted_at']
    
    @property
    def is_graded(self):
        """Check if submission has been graded"""
        return self.marks_obtained is not None
    
    def save(self, *args, **kwargs):
        """Auto-update status when graded"""
        if self.marks_obtained is not None:
            self.status = 'graded'
        else:
            self.status = 'submitted'
        super().save(*args, **kwargs)

class StudentProgressReview(models.Model):
    """
    Weekly progress review for each student
    Mentor can add feedback (internal and public)
    """
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='progress_reviews')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='progress_reviews')
    week_number = models.IntegerField(help_text="Week number (1, 2, 3, etc.)")
    
    # Feedback
    mentor_feedback = models.TextField(blank=True, null=True, help_text="Only visible to mentor and admin")
    student_feedback = models.TextField(blank=True, null=True, help_text="Visible to student")
    
    # Metadata
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='given_progress_reviews')
    reviewed_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.student.username} - Week {self.week_number} - {self.batch.name}"
    
    class Meta:
        unique_together = ['batch', 'student', 'week_number']
        ordering = ['-week_number', 'student__first_name']
