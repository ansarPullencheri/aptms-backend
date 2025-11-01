from rest_framework import serializers
from .models import Course, Batch
from authentication.serializers import UserSerializer


class CourseSerializer(serializers.ModelSerializer):
    mentor = UserSerializer(read_only=True)
    mentor_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    syllabus = serializers.FileField(required=False, allow_null=True)  # ✅ Add this
    
    class Meta:
        model = Course
        fields = [
            'id', 'name', 'code', 'description', 'duration_weeks',
            'syllabus', 'mentor', 'mentor_id', 'is_active',  # ✅ Include syllabus
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        mentor_id = validated_data.pop('mentor_id', None)
        course = Course.objects.create(**validated_data)
        
        if mentor_id:
            from authentication.models import User
            try:
                mentor = User.objects.get(id=mentor_id, role='mentor')
                course.mentor = mentor
                course.save()
            except User.DoesNotExist:
                pass
        
        return course
    
    def update(self, instance, validated_data):
        mentor_id = validated_data.pop('mentor_id', None)
        
        # Update all fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if mentor_id is not None:
            from authentication.models import User
            try:
                mentor = User.objects.get(id=mentor_id, role='mentor')
                instance.mentor = mentor
            except User.DoesNotExist:
                pass
        
        instance.save()
        return instance


class BatchSerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
    course_id = serializers.IntegerField(write_only=True)
    mentor = UserSerializer(read_only=True)
    mentor_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    student_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Batch
        fields = [
            'id', 'name', 'course', 'course_id', 'start_date', 'end_date',
            'mentor', 'mentor_id', 'max_students', 'student_count',
            'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_student_count(self, obj):
        return obj.students.filter(is_approved=True).count()


class BatchDetailSerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
    mentor = UserSerializer(read_only=True)
    students = UserSerializer(many=True, read_only=True)
    student_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Batch
        fields = [
            'id', 'name', 'course', 'start_date', 'end_date',
            'mentor', 'students', 'student_count', 'max_students',
            'is_active', 'created_at'
        ]
    
    def get_student_count(self, obj):
        return obj.students.filter(is_approved=True).count()
