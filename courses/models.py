from django.db import models
from authentication.models import User

class Course(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField()
    duration_weeks = models.IntegerField()
    mentor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                               related_name='courses_teaching', limit_choices_to={'role': 'mentor'})
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses_created')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['-created_at']

class Batch(models.Model):
    name = models.CharField(max_length=100)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='batches')
    start_date = models.DateField()
    end_date = models.DateField()
    mentor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='batches_mentoring', limit_choices_to={'role': 'mentor'})
    students = models.ManyToManyField(User, related_name='enrolled_batches', 
                                     limit_choices_to={'role': 'student'})
    max_students = models.IntegerField(default=30)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} - {self.course.name}"
    
    class Meta:
        ordering = ['-start_date']
        verbose_name_plural = 'Batches'
