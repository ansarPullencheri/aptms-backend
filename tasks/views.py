from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from .models import Task, TaskSubmission, StudentProgressReview  
from .serializers import (
    TaskSerializer, 
    TaskSubmissionSerializer, 
    GradeSubmissionSerializer,
    StudentTaskSerializer
)
from courses.models import Course, Batch
from authentication.models import User
from authentication.permissions import IsAdmin, IsMentor, IsStudent, IsAdminOrMentor

# Import notification utilities
try:
    from notifications.utils import (
        notify_on_task_submission,
        notify_on_task_graded,
        notify_on_task_created
    )
except ImportError:
    def notify_on_task_submission(*args, **kwargs):
        pass
    def notify_on_task_graded(*args, **kwargs):
        pass
    def notify_on_task_created(*args, **kwargs):
        pass


# ===== Task Views =====
class TaskListView(generics.ListAPIView):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.role == 'admin':
            return Task.objects.all()
        elif self.request.user.role == 'student':
            return Task.objects.filter(assigned_to=self.request.user)
        else:  # mentor
            return Task.objects.filter(
                Q(batch__mentor=self.request.user) | 
                Q(task_type='course', course__batches__mentor=self.request.user)
            ).distinct()


class TaskDetailView(generics.RetrieveAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]


class TaskCreateView(generics.CreateAPIView):
    """
    View for admins to create tasks.
    - Course-wide tasks: Assigned to all students in all batches of a course
    - Batch-specific tasks: Assigned to students in a specific batch
    """
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    
    def create(self, request, *args, **kwargs):
        try:
            course_id = request.data.get('course_id')
            batch_id = request.data.get('batch_id')
            task_type = request.data.get('task_type', 'batch')
            assigned_to_ids = request.data.get('assigned_to_ids', [])
            
            # Validate course_id
            if not course_id:
                return Response(
                    {'error': 'course_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate course exists
            try:
                course = Course.objects.get(id=course_id)
            except Course.DoesNotExist:
                return Response(
                    {'error': 'Course not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Handle batch-specific tasks
            if task_type == 'batch':
                if not batch_id:
                    return Response(
                        {'error': 'batch_id is required for batch-specific tasks'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                try:
                    batch = Batch.objects.get(id=batch_id, course=course)
                except Batch.DoesNotExist:
                    return Response(
                        {'error': 'Batch not found or does not belong to this course'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                # If no students specified, assign to all batch students
                if not assigned_to_ids:
                    batch_students = batch.students.filter(is_approved=True)
                    assigned_to_ids = list(batch_students.values_list('id', flat=True))
                    
                    if not assigned_to_ids:
                        return Response(
                            {'error': 'No approved students found in this batch'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
            
            # Prepare data for serializer
            task_data = {
                'title': request.data.get('title'),
                'description': request.data.get('description'),
                'course_id': course_id,
                'batch_id': batch_id if task_type == 'batch' else None,
                'task_type': task_type,
                'assigned_to_ids': assigned_to_ids if task_type == 'batch' else [],
                'due_date': request.data.get('due_date'),
                'max_marks': request.data.get('max_marks', 100),
            }
            
            # Create task using serializer
            serializer = self.get_serializer(data=task_data)
            serializer.is_valid(raise_exception=True)
            task = serializer.save(created_by=request.user)
            
            #  SEND NOTIFICATION TO STUDENTS AND MENTOR
            notify_on_task_created(task, request.user)
            
            # Get count of assigned students
            student_count = task.assigned_to.count()
            
            # Build response message
            if task_type == 'course':
                message = f'Course-wide task created and assigned to {student_count} student(s) across all batches of {course.name}'
            else:
                message = f'Task created and assigned to {student_count} student(s) in {batch.name}'
            
            return Response(
                {
                    'message': message,
                    'task': TaskSerializer(task).data
                },
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class TaskUpdateView(generics.UpdateAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]


class TaskDeleteView(generics.DestroyAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        task_title = instance.title
        self.perform_destroy(instance)
        return Response(
            {'message': f'Task "{task_title}" deleted successfully'},
            status=status.HTTP_200_OK
        )


class AssignedTasksView(generics.ListAPIView):
    """View for students to see their assigned tasks."""
    serializer_class = StudentTaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    
    def get_queryset(self):
        return Task.objects.filter(assigned_to=self.request.user).order_by('-created_at')
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


# ===== Submission Views =====
class TaskSubmissionView(generics.CreateAPIView):
    serializer_class = TaskSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    
    def create(self, request, task_id):
        try:
            task = Task.objects.get(id=task_id, assigned_to=request.user)
        except Task.DoesNotExist:
            return Response(
                {'error': 'Task not found or not assigned to you'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if already submitted
        if TaskSubmission.objects.filter(task=task, student=request.user).exists():
            return Response(
                {'error': 'You have already submitted this task'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        submission = serializer.save(student=request.user, task=task)
        
        # SEND NOTIFICATION TO MENTOR AND ADMIN
        notify_on_task_submission(task, request.user, submission)
        
        return Response(
            {
                'message': 'Task submitted successfully',
                'submission': serializer.data
            },
            status=status.HTTP_201_CREATED
        )


class SubmissionListView(generics.ListAPIView):
    serializer_class = TaskSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.role == 'student':
            return TaskSubmission.objects.filter(student=self.request.user)
        elif self.request.user.role == 'mentor':
            return TaskSubmission.objects.filter(
                Q(task__batch__mentor=self.request.user) |
                Q(task__task_type='course', task__course__batches__mentor=self.request.user)
            ).distinct()
        else:  # admin
            return TaskSubmission.objects.all()


class SubmissionDetailView(generics.RetrieveAPIView):
    queryset = TaskSubmission.objects.all()
    serializer_class = TaskSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]


class GradeSubmissionView(generics.UpdateAPIView):
    queryset = TaskSubmission.objects.all()
    serializer_class = GradeSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrMentor]
    
    def perform_update(self, serializer):
        submission = serializer.save(graded_by=self.request.user)
        
        # SEND NOTIFICATION TO STUDENT
        notify_on_task_graded(submission, self.request.user)


# ===== Mentor-Specific Task Views =====
class MentorBatchTasksView(generics.ListAPIView):
    """View for mentors to see all tasks for their assigned batches."""
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsMentor]
    
    def get_queryset(self):
        batch_id = self.kwargs.get('batch_id')
        batch = Batch.objects.get(id=batch_id, mentor=self.request.user)
        
        # Get both batch-specific tasks and course-wide tasks
        return Task.objects.filter(
            Q(batch=batch) | 
            Q(task_type='course', course=batch.course)
        ).prefetch_related('assigned_to', 'submissions').distinct()


class StudentSubmittedTasksView(generics.ListAPIView):
    """View for mentors to see all submitted tasks by a specific student."""
    serializer_class = TaskSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrMentor]
    
    def get_queryset(self):
        student_id = self.kwargs.get('student_id')
        
        if self.request.user.role == 'admin':
            return TaskSubmission.objects.filter(
                student_id=student_id
            ).select_related('task', 'student', 'graded_by')
        
        # For mentors, only show submissions for their batches or course-wide tasks
        return TaskSubmission.objects.filter(
            student_id=student_id
        ).filter(
            Q(task__batch__mentor=self.request.user) |
            Q(task__task_type='course', task__course__batches__mentor=self.request.user)
        ).select_related('task', 'student', 'graded_by').distinct()


class StudentAssignedTasksView(generics.ListAPIView):
    """View for mentors to see all assigned tasks for a specific student."""
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrMentor]
    
    def get_queryset(self):
        student_id = self.kwargs.get('student_id')
        
        if self.request.user.role == 'admin':
            return Task.objects.filter(
                assigned_to__id=student_id
            ).prefetch_related('assigned_to', 'submissions')
        
        # For mentors, only show tasks from their batches or course-wide tasks
        return Task.objects.filter(
            assigned_to__id=student_id
        ).filter(
            Q(batch__mentor=self.request.user) |
            Q(task_type='course', course__batches__mentor=self.request.user)
        ).prefetch_related('assigned_to', 'submissions').distinct()


class BatchTaskSubmissionsView(APIView):
    """View to get all task submissions for a specific batch."""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrMentor]
    
    def get(self, request, batch_id):
        try:
            if request.user.role == 'admin':
                batch = Batch.objects.get(id=batch_id)
            else:
                batch = Batch.objects.get(id=batch_id, mentor=request.user)
            
            # Get both batch-specific and course-wide tasks
            tasks = Task.objects.filter(
                Q(batch=batch) | 
                Q(task_type='course', course=batch.course)
            ).prefetch_related(
                'submissions__student',
                'assigned_to'
            ).distinct()
            
            task_data = []
            for task in tasks:
                # Filter submissions for students in this batch
                batch_student_ids = batch.students.values_list('id', flat=True)
                submissions = task.submissions.filter(student_id__in=batch_student_ids)
                
                task_info = {
                    'task_id': task.id,
                    'task_title': task.title,
                    'task_type': task.task_type,
                    'due_date': task.due_date,
                    'max_marks': task.max_marks,
                    'total_assigned': task.assigned_to.filter(id__in=batch_student_ids).count(),
                    'total_submitted': submissions.count(),
                    'submissions': [
                        {
                            'submission_id': sub.id,
                            'student_name': f"{sub.student.first_name} {sub.student.last_name}",
                            'student_email': sub.student.email,
                            'submitted_at': sub.submitted_at,
                            'marks_obtained': sub.marks_obtained,
                            'is_graded': sub.marks_obtained is not None,
                        }
                        for sub in submissions
                    ]
                }
                task_data.append(task_info)
            
            return Response({
                'batch_id': batch.id,
                'batch_name': batch.name,
                'course_name': batch.course.name,
                'tasks': task_data
            })
            
        except Batch.DoesNotExist:
            return Response(
                {'error': 'Batch not found or you do not have access'},
                status=status.HTTP_404_NOT_FOUND
            )


# ===== Mentor Submission Views (NEW) =====
class MentorPendingSubmissionsView(APIView):
    """
    View for mentors to see all pending submissions (not yet graded) 
    from students in their batches
    """
    permission_classes = [permissions.IsAuthenticated, IsMentor]
    
    def get(self, request):
        try:
            mentor = request.user
            
            # Get all batches this mentor is teaching
            mentor_batches = Batch.objects.filter(mentor=mentor)
            
            # Get all tasks from these batches
            mentor_tasks = Task.objects.filter(batch__in=mentor_batches)
            
            # Get pending submissions (not graded yet)
            pending_submissions = TaskSubmission.objects.filter(
                task__in=mentor_tasks,
                marks_obtained__isnull=True
            ).select_related('task', 'student', 'task__batch', 'task__course').order_by('-submitted_at')
            
            submissions_data = []
            for submission in pending_submissions:
                submissions_data.append({
                    'id': submission.id,
                    'student': {
                        'id': submission.student.id,
                        'name': f"{submission.student.first_name} {submission.student.last_name}",
                        'username': submission.student.username,
                        'email': submission.student.email,
                    },
                    'task': {
                        'id': submission.task.id,
                        'title': submission.task.title,
                        'description': submission.task.description,
                        'max_marks': submission.task.max_marks,
                        'due_date': submission.task.due_date,
                        'course': {
                            'id': submission.task.course.id,
                            'name': submission.task.course.name,
                        },
                        'batch': {
                            'id': submission.task.batch.id,
                            'name': submission.task.batch.name,
                        } if submission.task.batch else None,
                    },
                    'submission_text': submission.submission_text,
                    'submission_file': request.build_absolute_uri(submission.submission_file.url) if submission.submission_file else None,
                    'submitted_at': submission.submitted_at,
                    'status': submission.status,
                })
            
            return Response({
                'pending_submissions': submissions_data,
                'total_pending': len(submissions_data),
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class MentorSubmissionDetailView(APIView):
    """
    View for mentor to see detailed submission including file and text
    """
    permission_classes = [permissions.IsAuthenticated, IsMentor]
    
    def get(self, request, submission_id):
        try:
            mentor = request.user
            
            submission = TaskSubmission.objects.select_related(
                'task', 'student', 'task__batch', 'task__course'
            ).get(id=submission_id)
            
            # Verify mentor has access
            if submission.task.batch:
                if submission.task.batch.mentor != mentor:
                    return Response({
                        'error': 'You do not have access to this submission'
                    }, status=status.HTTP_403_FORBIDDEN)
            else:
                has_access = Batch.objects.filter(
                    mentor=mentor,
                    course=submission.task.course
                ).exists()
                
                if not has_access:
                    return Response({
                        'error': 'You do not have access to this submission'
                    }, status=status.HTTP_403_FORBIDDEN)
            
            # Build response
            submission_data = {
                'id': submission.id,
                'student': {
                    'id': submission.student.id,
                    'name': f"{submission.student.first_name} {submission.student.last_name}",
                    'username': submission.student.username,
                    'email': submission.student.email,
                    'phone': getattr(submission.student, 'phone', ''),
                },
                'task': {
                    'id': submission.task.id,
                    'title': submission.task.title,
                    'description': submission.task.description,
                    'max_marks': submission.task.max_marks,
                    'due_date': submission.task.due_date,
                    'course': {
                        'id': submission.task.course.id,
                        'name': submission.task.course.name,
                    },
                    'batch': {
                        'id': submission.task.batch.id,
                        'name': submission.task.batch.name,
                    } if submission.task.batch else None,
                },
                'submission_text': submission.submission_text or '',
                'submission_file': request.build_absolute_uri(submission.submission_file.url) if submission.submission_file else None,
                'submitted_at': submission.submitted_at,
                'status': submission.status,
                'marks_obtained': submission.marks_obtained,
                'feedback': submission.feedback or '',
                'is_graded': submission.marks_obtained is not None,
            }
            
            return Response(submission_data, status=status.HTTP_200_OK)
            
        except TaskSubmission.DoesNotExist:
            return Response({
                'error': f'Submission not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class MentorGradeSubmissionView(APIView):
    """
    View for mentor to grade a submission
    """
    permission_classes = [permissions.IsAuthenticated, IsMentor]
    
    def post(self, request, submission_id):
        try:
            mentor = request.user
            
            # Get submission
            submission = TaskSubmission.objects.select_related(
                'task', 'student', 'task__batch'
            ).get(id=submission_id)
            
            # Verify mentor has access
            if submission.task.batch and submission.task.batch.mentor != mentor:
                return Response({
                    'error': 'You do not have access to this submission'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Get data
            marks_obtained = request.data.get('marks_obtained')
            feedback = request.data.get('feedback', '')
            
            if marks_obtained is None:
                return Response({
                    'error': 'marks_obtained is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate marks
            try:
                marks_obtained = float(marks_obtained)
            except (TypeError, ValueError):
                return Response({
                    'error': 'marks_obtained must be a number'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if marks_obtained < 0 or marks_obtained > submission.task.max_marks:
                return Response({
                    'error': f'Marks must be between 0 and {submission.task.max_marks}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Update submission
            submission.marks_obtained = marks_obtained
            submission.feedback = feedback
            submission.graded_by = mentor
            submission.status = 'graded'
            submission.save()
            
            #  Send notification to student
            notify_on_task_graded(submission, mentor)
            
            return Response({
                'message': 'Submission graded successfully',
                'submission': {
                    'id': submission.id,
                    'student_name': f"{submission.student.first_name} {submission.student.last_name}",
                    'task_title': submission.task.title,
                    'marks_obtained': submission.marks_obtained,
                    'feedback': submission.feedback,
                }
            }, status=status.HTTP_200_OK)
            
        except TaskSubmission.DoesNotExist:
            return Response({
                'error': 'Submission not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class MentorGradedSubmissionsView(APIView):
    """
    View for mentor to see all graded submissions
    """
    permission_classes = [permissions.IsAuthenticated, IsMentor]
    
    def get(self, request):
        try:
            mentor = request.user
            
            # Get all batches this mentor is teaching
            mentor_batches = Batch.objects.filter(mentor=mentor)
            
            # Get all tasks from these batches
            mentor_tasks = Task.objects.filter(batch__in=mentor_batches)
            
            # Get graded submissions
            graded_submissions = TaskSubmission.objects.filter(
                task__in=mentor_tasks,
                marks_obtained__isnull=False
            ).select_related('task', 'student', 'task__batch', 'task__course').order_by('-submitted_at')
            
            submissions_data = []
            for submission in graded_submissions:
                percentage = (submission.marks_obtained / submission.task.max_marks * 100) if submission.task.max_marks > 0 else 0
                submissions_data.append({
                    'id': submission.id,
                    'student': {
                        'id': submission.student.id,
                        'name': f"{submission.student.first_name} {submission.student.last_name}",
                        'username': submission.student.username,
                    },
                    'task': {
                        'id': submission.task.id,
                        'title': submission.task.title,
                        'max_marks': submission.task.max_marks,
                        'course': {
                            'id': submission.task.course.id,
                            'name': submission.task.course.name,
                        },
                    },
                    'marks_obtained': submission.marks_obtained,
                    'percentage': round(percentage, 2),
                    'submitted_at': submission.submitted_at,
                    'graded_by': f"{submission.graded_by.first_name} {submission.graded_by.last_name}" if submission.graded_by else 'Unknown',
                })
            
            return Response({
                'graded_submissions': submissions_data,
                'total_graded': len(submissions_data),
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class MentorCreateTaskView(APIView):
    """Mentors can create tasks for their assigned batches"""
    permission_classes = [permissions.IsAuthenticated, IsMentor]
    
    def post(self, request):
        try:
            batch_id = request.data.get('batch_id')
            assigned_to_ids = request.data.get('assigned_to_ids', [])
            
            # Get batch and verify mentor owns it
            batch = Batch.objects.get(id=batch_id, mentor=request.user)
            
            # Create task
            task = Task.objects.create(
                course=batch.course,
                batch=batch,
                title=request.data.get('title'),
                description=request.data.get('description'),
                due_date=request.data.get('due_date'),
                max_marks=request.data.get('max_marks', 100),
                created_by=request.user
            )
            
            # Assign to students
            if assigned_to_ids:
                students = batch.students.filter(id__in=assigned_to_ids, is_approved=True)
                task.assigned_to.set(students)
            else:
                students = batch.students.filter(is_approved=True)
                task.assigned_to.set(students)
            
            #  SEND NOTIFICATION TO STUDENTS AND ADMIN
            notify_on_task_created(task, request.user)
            
            return Response({
                'message': f'Task created and assigned to {students.count()} student(s)',
                'task_id': task.id
            }, status=status.HTTP_201_CREATED)
            
        except Batch.DoesNotExist:
            return Response(
                {'error': 'Batch not found or you do not have access'},
                status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class MentorTasksListView(APIView):
    """View for mentors to see ALL tasks assigned to students in their batches"""
    permission_classes = [permissions.IsAuthenticated, IsMentor]
    
    def get(self, request):
        try:
            # Get all batches assigned to this mentor
            mentor_batches = Batch.objects.filter(mentor=request.user)
            
            # Get courses from mentor's batches
            mentor_courses = set(batch.course for batch in mentor_batches)
            
            # Get ALL tasks:
            # 1. Tasks assigned to mentor's specific batches
            # 2. Course-wide tasks (batch=NULL) for courses where mentor has batches
            tasks = Task.objects.filter(
                Q(batch__in=mentor_batches) |  # Batch-specific tasks
                Q(batch__isnull=True, course__in=mentor_courses)  # Course-wide tasks
            ).select_related('course', 'batch', 'created_by').order_by('-created_at')
            
            tasks_data = []
            for task in tasks:
                # Get submission count
                if task.batch:
                    submission_count = TaskSubmission.objects.filter(task=task).count()
                    graded_count = TaskSubmission.objects.filter(
                        task=task, 
                        marks_obtained__isnull=False
                    ).count()
                    total_students = task.assigned_to.count()
                else:
                    # For course-wide tasks, count submissions from ALL students in mentor's batches
                    course_students = set()
                    for batch in mentor_batches.filter(course=task.course):
                        course_students.update(batch.students.filter(is_approved=True))
                    
                    submission_count = TaskSubmission.objects.filter(
                        task=task,
                        student__in=course_students
                    ).count()
                    graded_count = TaskSubmission.objects.filter(
                        task=task,
                        student__in=course_students,
                        marks_obtained__isnull=False
                    ).count()
                    total_students = len(course_students)
                
                # Determine who created the task
                creator_role = task.created_by.role if task.created_by else 'Unknown'
                creator_name = f"{task.created_by.first_name} {task.created_by.last_name}" if task.created_by else 'Unknown'
                
                tasks_data.append({
                    'id': task.id,
                    'title': task.title,
                    'description': task.description,
                    'course_name': task.course.name,
                    'batch_name': task.batch.name if task.batch else 'All Batches',
                    'batch_id': task.batch.id if task.batch else None,
                    'is_course_wide': task.batch is None,
                    'due_date': task.due_date,
                    'max_marks': task.max_marks,
                    'created_at': task.created_at,
                    'created_by_role': creator_role,
                    'created_by_name': creator_name,
                    'is_my_task': task.created_by == request.user if task.created_by else False,
                    'total_students': total_students,
                    'submission_count': submission_count,
                    'graded_count': graded_count,
                    'pending_grading': submission_count - graded_count,
                })
            
            return Response({
                'tasks': tasks_data,
                'total_tasks': len(tasks_data),
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# ===== Student Views =====
class StudentSubmitTaskView(APIView):
    """View for students to submit tasks"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            # Verify student role
            if request.user.role != 'student':
                return Response(
                    {'error': 'Only students can submit tasks'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get task_id from request
            task_id = request.data.get('task_id')
            if not task_id:
                return Response(
                    {'error': 'task_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            submission_text = request.data.get('submission_text', '')
            submission_file = request.FILES.get('submission_file')
            
            # Validate that at least one submission method is provided
            if not submission_text and not submission_file:
                return Response(
                    {'error': 'Please provide either submission text or a file'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get task
            try:
                task = Task.objects.get(id=task_id)
            except Task.DoesNotExist:
                return Response(
                    {'error': 'Task not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check if student is assigned using filter().exists()
            if not task.assigned_to.filter(id=request.user.id).exists():
                return Response(
                    {'error': 'You are not assigned to this task'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check if already submitted
            existing_submission = TaskSubmission.objects.filter(
                task=task,
                student=request.user
            ).first()
            
            if existing_submission:
                return Response(
                    {'error': 'You have already submitted this task'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create submission
            submission = TaskSubmission.objects.create(
                task=task,
                student=request.user,
                submission_text=submission_text,
                submission_file=submission_file,
                status='submitted'
            )
            
            #  SEND NOTIFICATION TO MENTOR AND ADMIN
            notify_on_task_submission(task, request.user, submission)
            
            return Response({
                'message': 'Task submitted successfully',
                'submission_id': submission.id,
                'submitted_at': submission.submitted_at,
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            # Log the error for debugging
            import traceback
            print(traceback.format_exc())
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class StudentTaskDetailView(APIView):
    """View for students to see task details"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, task_id):
        try:
            if request.user.role != 'student':
                return Response(
                    {'error': 'Only students can access this endpoint'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get task
            task = Task.objects.select_related('course', 'batch', 'created_by').get(id=task_id)
            
            # Check if student is assigned to this task
            if request.user not in task.assigned_to.all():
                return Response(
                    {'error': 'You are not assigned to this task'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check if already submitted
            submission = TaskSubmission.objects.filter(
                task=task,
                student=request.user
            ).first()
            
            task_data = {
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'course': {
                    'id': task.course.id,
                    'name': task.course.name,
                    'code': task.course.code,
                },
                'batch': {
                    'id': task.batch.id if task.batch else None,
                    'name': task.batch.name if task.batch else 'Course-Wide',
                } if task.batch else None,
                'due_date': task.due_date,
                'max_marks': task.max_marks,
                'created_at': task.created_at,
                'created_by': {
                    'name': f"{task.created_by.first_name} {task.created_by.last_name}" if task.created_by else 'Unknown',
                    'role': task.created_by.role if task.created_by else 'Unknown',
                },
                'is_submitted': submission is not None,
                'submission': {
                    'id': submission.id,
                    'submitted_at': submission.submitted_at,
                    'submission_text': submission.submission_text,
                    'submission_file': request.build_absolute_uri(submission.submission_file.url) if submission.submission_file else None,
                    'marks_obtained': submission.marks_obtained,
                    'feedback': submission.feedback,
                    'status': submission.status,
                } if submission else None,
            }
            
            return Response(task_data)
            
        except Task.DoesNotExist:
            return Response(
                {'error': 'Task not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# ===== Weekly Progress Review Views =====
class MentorWeeklyReviewView(APIView):
    """
    GET: Fetch existing weekly review for a student
    POST: Save weekly review for a student
    """
    permission_classes = [permissions.IsAuthenticated, IsMentor]
    
    def get(self, request, batch_id, student_id, week_number):
        try:
            mentor = request.user
            batch_id = int(batch_id)
            student_id = int(student_id)
            week_number = int(week_number)
            
            # Verify mentor access to batch
            batch = Batch.objects.get(id=batch_id, mentor=mentor)
            
            # Verify student is in batch
            if not batch.students.filter(id=student_id).exists():
                return Response({
                    'error': 'Student not in this batch'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Get or create progress review
            progress_review, created = StudentProgressReview.objects.get_or_create(
                batch_id=batch_id,
                student_id=student_id,
                week_number=week_number
            )
            
            review_data = {
                'id': progress_review.id,
                'batch': {
                    'id': batch.id,
                    'name': batch.name,
                },
                'student': {
                    'id': progress_review.student.id,
                    'name': f"{progress_review.student.first_name} {progress_review.student.last_name}",
                    'username': progress_review.student.username,
                    'email': progress_review.student.email,
                },
                'week_number': week_number,
                'mentor_feedback': progress_review.mentor_feedback or '',
                'student_feedback': progress_review.student_feedback or '',
                'reviewed_at': progress_review.reviewed_at,
                'reviewed_by': {
                    'name': f"{progress_review.reviewed_by.first_name} {progress_review.reviewed_by.last_name}",
                    'username': progress_review.reviewed_by.username,
                } if progress_review.reviewed_by else None,
            }
            
            return Response(review_data, status=status.HTTP_200_OK)
            
        except Batch.DoesNotExist:
            return Response({
                'error': 'Batch not found or you do not have access'
            }, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    def post(self, request, batch_id, student_id, week_number):
        try:
            mentor = request.user
            batch_id = int(batch_id)
            student_id = int(student_id)
            week_number = int(week_number)
            
            # Verify mentor access
            batch = Batch.objects.get(id=batch_id, mentor=mentor)
            
            # Verify student is in batch
            if not batch.students.filter(id=student_id).exists():
                return Response({
                    'error': 'Student not in this batch'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Get data from request
            mentor_feedback = request.data.get('mentor_feedback', '')
            student_feedback = request.data.get('student_feedback', '')
            
            # Get or create progress review
            progress_review, created = StudentProgressReview.objects.get_or_create(
                batch_id=batch_id,
                student_id=student_id,
                week_number=week_number
            )
            
            # Update feedback
            progress_review.mentor_feedback = mentor_feedback if mentor_feedback else None
            progress_review.student_feedback = student_feedback if student_feedback else None
            progress_review.reviewed_by = mentor
            progress_review.save()
            
            return Response({
                'message': 'Progress review saved successfully',
                'review_id': progress_review.id,
                'week_number': week_number,
                'batch_id': batch_id,
                'student_id': student_id,
                'mentor_feedback': progress_review.mentor_feedback,
                'student_feedback': progress_review.student_feedback,
            }, status=status.HTTP_200_OK)
            
        except Batch.DoesNotExist:
            return Response({
                'error': 'Batch not found'
            }, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)



class BatchStudentsWeeklyListView(APIView):
    """
    Get all students in a batch for weekly review selection
    """
    permission_classes = [permissions.IsAuthenticated, IsMentor]
    
    def get(self, request, batch_id):
        try:
            mentor = request.user
            
            # Verify mentor access
            batch = Batch.objects.get(id=batch_id, mentor=mentor)
            
            # Get all approved students
            students = batch.students.filter(is_approved=True).values(
                'id', 'first_name', 'last_name', 'username', 'email'
            )
            
            students_list = [
                {
                    'id': s['id'],
                    'name': f"{s['first_name']} {s['last_name']}",
                    'username': s['username'],
                    'email': s['email'],
                }
                for s in students
            ]
            
            return Response({
                'batch_id': batch.id,
                'batch_name': batch.name,
                'course_name': batch.course.name,
                'students': students_list,
            }, status=status.HTTP_200_OK)
            
        except Batch.DoesNotExist:
            return Response({
                'error': 'Batch not found'
            }, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class StudentWeeklyReviewView(APIView):
    """
    GET: Student can view their weekly feedback
    Fetches feedback for a specific week without needing batch_id
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, week_number):
        try:
            student = request.user
            
            print(f" Student {student.username} fetching week {week_number} feedback")
            
      
            from courses.models import Batch 
            
            student_batch = Batch.objects.filter(students=student).first()
            
            if not student_batch:
                print(f"⚠️ Student {student.username} not enrolled in any batch")
                return Response({
                    'id': None,
                    'batch': None,
                    'week_number': week_number,
                    'student_feedback': '',
                    'mentor_feedback': '',
                    'reviewed_at': None,
                    'reviewed_by': None,
                    'message': 'You are not enrolled in any batch'
                }, status=status.HTTP_200_OK)
            
            batch = student_batch
            print(f"Found batch: {batch.name}")
            
            #  Try to get progress review for this week
            try:
                progress_review = StudentProgressReview.objects.get(
                    batch=batch,
                    student=student,
                    week_number=week_number
                )
                
                print(f" Week {week_number} review found for {student.username}")
                
                review_data = {
                    'id': progress_review.id,
                    'batch': {
                        'id': batch.id,
                        'name': batch.name,
                    },
                    'week_number': week_number,
                    'student_feedback': progress_review.student_feedback or '',
                    'mentor_feedback': progress_review.mentor_feedback or '',
                    'reviewed_at': progress_review.reviewed_at,
                    'reviewed_by': {
                        'name': f"{progress_review.reviewed_by.first_name} {progress_review.reviewed_by.last_name}",
                        'username': progress_review.reviewed_by.username,
                    } if progress_review.reviewed_by else None,
                }
                
                return Response(review_data, status=status.HTTP_200_OK)
                
            except StudentProgressReview.DoesNotExist:
                print(f"⚠️ Week {week_number} review not found for {student.username}")
                
                # Return empty feedback (no error)
                return Response({
                    'id': None,
                    'batch': {
                        'id': batch.id,
                        'name': batch.name,
                    },
                    'week_number': week_number,
                    'student_feedback': '',
                    'mentor_feedback': '',
                    'reviewed_at': None,
                    'reviewed_by': None,
                    'message': 'No feedback for this week yet'
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            print(f" Error in StudentWeeklyReviewView: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({
                'error': f'Error fetching feedback: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)

class MentorAllReviewsView(APIView):
    """Get all reviews created by the mentor"""
    permission_classes = [permissions.IsAuthenticated, IsMentor]
    
    def get(self, request):
        try:
            mentor = request.user
            
            # Get all reviews where this mentor is the reviewer
            reviews = StudentProgressReview.objects.filter(
                reviewed_by=mentor
            ).select_related('student', 'batch', 'reviewed_by')
            
            reviews_data = []
            for review in reviews:
                reviews_data.append({
                    'id': review.id,
                    'student_name': f"{review.student.first_name} {review.student.last_name}",
                    'student_username': review.student.username,
                    'student_email': review.student.email,
                    'batch_name': review.batch.name,
                    'week_number': review.week_number,
                    'mentor_feedback': review.mentor_feedback or '',
                    'student_feedback': review.student_feedback or '',
                    'reviewed_at': review.reviewed_at.isoformat() if review.reviewed_at else None,
                })
            
            # Sort by most recent first
            reviews_data.sort(key=lambda x: x['reviewed_at'], reverse=True)
            
            return Response({
                'reviews': reviews_data,
                'count': len(reviews_data)
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)