from rest_framework import serializers
from .models import Task, TaskSubmission
from authentication.serializers import UserSerializer


class TaskSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.name', read_only=True)
    batch_name = serializers.CharField(source='batch.name', read_only=True, allow_null=True)
    created_by_name = serializers.SerializerMethodField()
    assigned_to_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    course_id = serializers.IntegerField(write_only=True)
    batch_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Task
        fields = [
            'id', 
            'title', 
            'description', 
            'course', 
            'course_id',
            'course_name', 
            'batch',
            'batch_id', 
            'batch_name', 
            'due_date', 
            'max_marks', 
            'created_by',
            'created_by_name',
            'created_at', 
            'updated_at',
            'assigned_to_ids',
            'task_type',
            'week_number',
            'task_order',
            'is_scheduled',
            'release_date',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'course', 'batch', 'created_by']
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}"
        return "Unknown"
    
    def create(self, validated_data):
        assigned_to_ids = validated_data.pop('assigned_to_ids', [])
        course_id = validated_data.pop('course_id')
        batch_id = validated_data.pop('batch_id', None)
        
        from courses.models import Course, Batch
        from authentication.models import User
        
        # Get course
        course = Course.objects.get(id=course_id)
        validated_data['course'] = course
        
        # Get batch if provided
        batch = None
        if batch_id:
            batch = Batch.objects.get(id=batch_id)
            validated_data['batch'] = batch
        
        # Create task
        task = Task.objects.create(**validated_data)
        
        # ✅ CRITICAL FIX: Handle task assignment based on task_type
        if validated_data.get('task_type') == 'course':
            # Course-wide task: assign to ALL approved students in ALL batches of this course
            batches = course.batches.all()
            all_students = User.objects.filter(
                role='student',
                is_approved=True,
                enrolled_batches__in=batches
            ).distinct()
            task.assigned_to.set(all_students)
            print(f"✅ Course-wide task '{task.title}': Assigned to {all_students.count()} students")
            print(f"   Students: {[s.username for s in all_students]}")
        else:
            # Batch-specific task
            if assigned_to_ids:
                # Specific students selected by admin
                students = User.objects.filter(
                    id__in=assigned_to_ids, 
                    role='student', 
                    is_approved=True
                )
                task.assigned_to.set(students)
                print(f"✅ Batch task '{task.title}': Assigned to {students.count()} specific students")
                print(f"   Students: {[s.username for s in students]}")
            elif batch:
                # No specific students: assign to ALL approved students in batch
                students = batch.students.filter(is_approved=True)
                task.assigned_to.set(students)
                print(f"✅ Batch task '{task.title}': Assigned to {students.count()} students in batch '{batch.name}'")
                print(f"   Students: {[s.username for s in students]}")
            else:
                print(f"⚠️ WARNING: Task '{task.title}' created but no students assigned!")
        
        # ✅ Final verification
        final_count = task.assigned_to.count()
        print(f"✅ TASK CREATION COMPLETE: '{task.title}' has {final_count} assigned students")
        
        return task


class TaskSubmissionSerializer(serializers.ModelSerializer):
    task_title = serializers.CharField(source='task.title', read_only=True)
    student_name = serializers.SerializerMethodField()
    
    class Meta:
        model = TaskSubmission
        fields = [
            'id',
            'task',
            'task_title',
            'student',
            'student_name',
            'submission_text',
            'submission_file',
            'submitted_at',
            'marks_obtained',
            'feedback',
            'graded_by',
        ]
        read_only_fields = ['id', 'submitted_at', 'student', 'graded_by']
    
    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"


class GradeSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskSubmission
        fields = ['marks_obtained', 'feedback']
    
    def validate_marks_obtained(self, value):
        if value < 0:
            raise serializers.ValidationError("Marks cannot be negative")
        if value > self.instance.task.max_marks:
            raise serializers.ValidationError(f"Marks cannot exceed {self.instance.task.max_marks}")
        return value


class StudentTaskSerializer(serializers.ModelSerializer):
    """Serializer for student view of tasks"""
    course_name = serializers.CharField(source='course.name', read_only=True)
    batch_name = serializers.CharField(source='batch.name', read_only=True, allow_null=True)
    is_submitted = serializers.SerializerMethodField()
    submission_status = serializers.SerializerMethodField()
    
    class Meta:
        model = Task
        fields = [
            'id',
            'title',
            'description',
            'course_name',
            'batch_name',
            'due_date',
            'max_marks',
            'created_at',
            'is_submitted',
            'submission_status',
            'task_order',
            'week_number',
        ]
    
    def get_is_submitted(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return TaskSubmission.objects.filter(
                task=obj,
                student=request.user
            ).exists()
        return False
    
    def get_submission_status(self, obj):
        request = self.context.get('request')
        if request and request.user:
            submission = TaskSubmission.objects.filter(
                task=obj,
                student=request.user
            ).first()
            if submission:
                return {
                    'submitted_at': submission.submitted_at,
                    'is_graded': submission.marks_obtained is not None,
                    'marks_obtained': submission.marks_obtained,
                }
        return None
