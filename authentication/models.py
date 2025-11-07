from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('mentor', 'Mentor'),
        ('student', 'Student'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    phone = models.CharField(max_length=15, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        """Auto-set role to 'admin' for superusers"""
        if self.is_superuser or self.is_staff:
            self.role = 'admin'
            self.is_approved = True
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.username} - {self.role}"
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'



# class StudentProfile(models.Model):
#     user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
#     enrollment_number = models.CharField(max_length=50, unique=True, blank=True, null=True)
#     date_of_birth = models.DateField(blank=True, null=True)
#     address = models.TextField(blank=True, null=True)
#     guardian_name = models.CharField(max_length=100, blank=True, null=True)
#     guardian_phone = models.CharField(max_length=15, blank=True, null=True)
    
#     def __str__(self):
#         return f"{self.user.username} - Student Profile"
    
#     class Meta:
#         verbose_name = 'Student Profile'
#         verbose_name_plural = 'Student Profiles'

class StudentProfile(models.Model):
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]

    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('O+', 'O+'), ('O-', 'O-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    enrollment_number = models.CharField(max_length=50, unique=True, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    guardian_name = models.CharField(max_length=100, blank=True, null=True)
    guardian_phone = models.CharField(max_length=15, blank=True, null=True)

    
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    blood_group = models.CharField(max_length=5, choices=BLOOD_GROUP_CHOICES, blank=True, null=True)
    photo = models.ImageField(upload_to="student_photos/", blank=True, null=True)
    def __str__(self):
        return f"{self.user.username} - Student Profile"


class MentorProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='mentor_profile')
    specialization = models.CharField(max_length=200, blank=True, null=True)
    experience_years = models.IntegerField(default=0)
    bio = models.TextField(blank=True, null=True)
    qualification = models.CharField(max_length=200, blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.username} - Mentor Profile"
    
    class Meta:
        verbose_name = 'Mentor Profile'
        verbose_name_plural = 'Mentor Profiles'
