from rest_framework import serializers
from .models import Course, Batch
from authentication.models import User
from authentication.serializers import UserSerializer

class CourseSerializer(serializers.ModelSerializer):
    mentor = UserSerializer(read_only=True)
    mentor_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='mentor'),
        source='mentor',
        write_only=True,
        required=False,
        allow_null=True
    )
    created_by = UserSerializer(read_only=True)
    batch_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = ['id', 'name', 'code', 'description', 'duration_weeks', 
                 'mentor', 'mentor_id', 'created_by', 'is_active', 
                 'created_at', 'updated_at', 'batch_count']
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
    
    def get_batch_count(self, obj):
        return obj.batches.count()

class BatchSerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
    course_id = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.all(),
        source='course',
        write_only=True
    )
    mentor = UserSerializer(read_only=True)
    mentor_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='mentor'),
        source='mentor',
        write_only=True,
        required=False,
        allow_null=True
    )
    student_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='student'),
        source='students',
        write_only=True,
        many=True,
        required=False
    )
    student_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Batch
        fields = ['id', 'name', 'course', 'course_id', 'start_date', 'end_date',
                 'mentor', 'mentor_id', 'student_ids', 'max_students',
                 'is_active', 'created_at', 'student_count']
        read_only_fields = ['id', 'created_at']
    
    def get_student_count(self, obj):
        return obj.students.count()

class BatchDetailSerializer(BatchSerializer):
    """Extended serializer with full student details"""
    students = UserSerializer(many=True, read_only=True)
    
    class Meta(BatchSerializer.Meta):
        fields = BatchSerializer.Meta.fields + ['students']
