from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Avg, Sum
from django.utils import timezone
from tasks.models import Task, TaskSubmission
from tasks.serializers import TaskSerializer, TaskSubmissionSerializer
from courses.models import Batch
from .permissions import IsStudent


class StudentDashboardView(APIView):
    """
    Main dashboard view for students showing overview of their academic status.
    ✅ Includes course_id for syllabus download
    """
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    
    def get(self, request):
        student = request.user
        
        # ✅ Get enrolled batches with course_id
        enrolled_batches = student.enrolled_batches.select_related('course', 'mentor')
        
        # Get task statistics
        total_assigned = Task.objects.filter(assigned_to=student).count()
        total_submitted = TaskSubmission.objects.filter(student=student).count()
        pending_tasks = total_assigned - total_submitted
        
        # Get graded submissions
        graded_submissions = TaskSubmission.objects.filter(
            student=student,
            marks_obtained__isnull=False
        )
        
        # Calculate average marks
        if graded_submissions.exists():
            avg_marks = graded_submissions.aggregate(avg=Avg('marks_obtained'))['avg']
            total_marks_obtained = graded_submissions.aggregate(total=Sum('marks_obtained'))['total']
            total_max_marks = sum([sub.task.max_marks for sub in graded_submissions])
            percentage = (total_marks_obtained / total_max_marks * 100) if total_max_marks > 0 else 0
        else:
            avg_marks = 0
            percentage = 0
            total_marks_obtained = 0
            total_max_marks = 0
        
        # Recent submissions
        recent_submissions = TaskSubmission.objects.filter(
            student=student
        ).select_related('task').order_by('-submitted_at')[:5]
        
        dashboard_data = {
            'student_info': {
                'name': f"{student.first_name} {student.last_name}",
                'email': student.email,
                'username': student.username,
            },
            'enrolled_batches': [
                {
                    'id': batch.id,
                    'name': batch.name,
                    'course_id': batch.course.id,  # ✅ Added course_id for syllabus download
                    'course_name': batch.course.name,
                    'mentor_name': f"{batch.mentor.first_name} {batch.mentor.last_name}" if batch.mentor else None,
                    'start_date': batch.start_date,
                    'end_date': batch.end_date,
                }
                for batch in enrolled_batches
            ],
            'task_statistics': {
                'total_assigned': total_assigned,
                'total_submitted': total_submitted,
                'pending_tasks': pending_tasks,
                'completion_rate': (total_submitted / total_assigned * 100) if total_assigned > 0 else 0,
            },
            'academic_progress': {
                'total_graded_tasks': graded_submissions.count(),
                'average_marks': round(avg_marks, 2) if avg_marks else 0,
                'total_marks_obtained': total_marks_obtained,
                'total_max_marks': total_max_marks,
                'overall_percentage': round(percentage, 2),
            },
            'recent_submissions': [
                {
                    'task_title': sub.task.title,
                    'submitted_at': sub.submitted_at,
                    'marks_obtained': sub.marks_obtained,
                    'max_marks': sub.task.max_marks,
                    'is_graded': sub.marks_obtained is not None,
                }
                for sub in recent_submissions
            ]
        }
        
        return Response(dashboard_data)


class StudentTasksView(APIView):
    """View for students to see their assigned tasks with progression logic"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            if request.user.role != 'student':
                return Response(
                    {'error': 'Only students can access this endpoint'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get all tasks assigned to student
            all_tasks = Task.objects.filter(
                assigned_to=request.user
            ).exclude(
                is_scheduled=True,
                release_date__gt=timezone.now()
            ).select_related('course', 'batch').order_by('week_number', 'task_order', 'created_at')
            
            tasks_data = []
            
            # Group tasks by course
            course_tasks = {}
            for task in all_tasks:
                course_id = task.course.id
                if course_id not in course_tasks:
                    course_tasks[course_id] = []
                course_tasks[course_id].append(task)
            
            # Process each course's tasks
            for course_id, tasks in course_tasks.items():
                for index, task in enumerate(tasks):
                    submission = TaskSubmission.objects.filter(
                        task=task,
                        student=request.user
                    ).first()
                    
                    is_locked = False
                    lock_reason = None
                    
                    # Check if task is scheduled
                    if task.is_scheduled and task.release_date:
                        if timezone.now() < task.release_date:
                            is_locked = True
                            lock_reason = f"Available from {task.release_date.strftime('%B %d, %Y at %I:%M %p')}"
                    
                    # Check previous task completion
                    if not is_locked and index > 0:
                        previous_task = tasks[index - 1]
                        previous_submission = TaskSubmission.objects.filter(
                            task=previous_task,
                            student=request.user
                        ).first()
                        
                        if not previous_submission:
                            is_locked = True
                            lock_reason = f"Complete '{previous_task.title}' first"
                        elif previous_submission.marks_obtained is None:
                            is_locked = True
                            lock_reason = f"Waiting for '{previous_task.title}' to be graded"
                        else:
                            percentage = (previous_submission.marks_obtained / previous_task.max_marks) * 100
                            if percentage < 70:
                                is_locked = True
                                lock_reason = f"Score at least 70% in '{previous_task.title}' (Current: {percentage:.1f}%)"
                    
                    task_info = {
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
                        'task_order': task.task_order,
                        'week_number': task.week_number,
                        'release_date': task.release_date if task.is_scheduled else None,
                        'is_locked': is_locked,
                        'lock_reason': lock_reason,
                        'is_submitted': submission is not None,
                        'submission': {
                            'id': submission.id,
                            'submitted_at': submission.submitted_at,
                            'marks_obtained': submission.marks_obtained,
                            'is_graded': submission.marks_obtained is not None,
                        } if submission else None,
                    }
                    
                    tasks_data.append(task_info)
            
            return Response(tasks_data)
            
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class StudentPendingTasksView(generics.ListAPIView):
    """
    View for students to see pending (not submitted) tasks.
    """
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    
    def get_queryset(self):
        student = self.request.user
        submitted_task_ids = TaskSubmission.objects.filter(
            student=student
        ).values_list('task_id', flat=True)
        
        return Task.objects.filter(
            assigned_to=student
        ).exclude(id__in=submitted_task_ids).order_by('due_date')


class StudentSubmittedTasksView(generics.ListAPIView):
    """
    View for students to see all their submitted tasks with grades.
    """
    serializer_class = TaskSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    
    def get_queryset(self):
        return TaskSubmission.objects.filter(
            student=self.request.user
        ).select_related('task', 'graded_by').order_by('-submitted_at')


class StudentAcademicProgressView(APIView):
    """
    Detailed academic progress view showing performance metrics.
    """
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    
    def get(self, request):
        student = request.user
        
        # Get all submissions with grades
        graded_submissions = TaskSubmission.objects.filter(
            student=student,
            marks_obtained__isnull=False
        ).select_related('task', 'task__course', 'task__batch')
        
        # Overall statistics
        if graded_submissions.exists():
            total_marks_obtained = graded_submissions.aggregate(total=Sum('marks_obtained'))['total']
            total_max_marks = sum([sub.task.max_marks for sub in graded_submissions])
            overall_percentage = (total_marks_obtained / total_max_marks * 100) if total_max_marks > 0 else 0
            average_marks = graded_submissions.aggregate(avg=Avg('marks_obtained'))['avg']
        else:
            total_marks_obtained = 0
            total_max_marks = 0
            overall_percentage = 0
            average_marks = 0
        
        # Course-wise performance
        courses_performance = {}
        for submission in graded_submissions:
            course_name = submission.task.course.name
            if course_name not in courses_performance:
                courses_performance[course_name] = {
                    'course_id': submission.task.course.id,
                    'course_name': course_name,
                    'tasks_graded': 0,
                    'marks_obtained': 0,
                    'max_marks': 0,
                }
            courses_performance[course_name]['tasks_graded'] += 1
            courses_performance[course_name]['marks_obtained'] += submission.marks_obtained
            courses_performance[course_name]['max_marks'] += submission.task.max_marks
        
        # Calculate percentage for each course
        for course in courses_performance.values():
            if course['max_marks'] > 0:
                course['percentage'] = round((course['marks_obtained'] / course['max_marks'] * 100), 2)
            else:
                course['percentage'] = 0
        
        # Recent grades
        recent_grades = [
            {
                'task_title': sub.task.title,
                'course_name': sub.task.course.name,
                'marks_obtained': sub.marks_obtained,
                'max_marks': sub.task.max_marks,
                'percentage': round((sub.marks_obtained / sub.task.max_marks * 100), 2),
                'submitted_at': sub.submitted_at,
                'feedback': sub.feedback,
            }
            for sub in graded_submissions.order_by('-submitted_at')[:10]
        ]
        
        progress_data = {
            'overall_statistics': {
                'total_graded_tasks': graded_submissions.count(),
                'total_marks_obtained': total_marks_obtained,
                'total_max_marks': total_max_marks,
                'overall_percentage': round(overall_percentage, 2),
                'average_marks': round(average_marks, 2) if average_marks else 0,
            },
            'course_wise_performance': list(courses_performance.values()),
            'recent_grades': recent_grades,
            'grade_distribution': self._get_grade_distribution(graded_submissions),
        }
        
        return Response(progress_data)
    
    def _get_grade_distribution(self, submissions):
        """Helper method to categorize grades"""
        distribution = {
            'A (90-100%)': 0,
            'B (80-89%)': 0,
            'C (70-79%)': 0,
            'D (60-69%)': 0,
            'F (Below 60%)': 0,
        }
        
        for sub in submissions:
            percentage = (sub.marks_obtained / sub.task.max_marks * 100)
            if percentage >= 90:
                distribution['A (90-100%)'] += 1
            elif percentage >= 80:
                distribution['B (80-89%)'] += 1
            elif percentage >= 70:
                distribution['C (70-79%)'] += 1
            elif percentage >= 60:
                distribution['D (60-69%)'] += 1
            else:
                distribution['F (Below 60%)'] += 1
        
        return distribution


class StudentTaskDetailView(APIView):
    """View for students to see task details"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, pk):
        try:
            if request.user.role != 'student':
                return Response(
                    {'error': 'Only students can access this endpoint'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            task = Task.objects.select_related('course', 'batch', 'created_by').get(id=pk)
            
            if not task.assigned_to.filter(id=request.user.id).exists():
                return Response(
                    {'error': 'You are not assigned to this task'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            is_locked = False
            lock_reason = None
            
            # Get all tasks for this course
            course_tasks = Task.objects.filter(
                course=task.course,
                assigned_to=request.user
            ).order_by('task_order', 'created_at')
            
            task_list = list(course_tasks)
            try:
                current_index = task_list.index(task)
                
                if current_index > 0:
                    previous_task = task_list[current_index - 1]
                    previous_submission = TaskSubmission.objects.filter(
                        task=previous_task,
                        student=request.user
                    ).first()
                    
                    if not previous_submission:
                        is_locked = True
                        lock_reason = f"You must complete '{previous_task.title}' first"
                    elif previous_submission.marks_obtained is None:
                        is_locked = True
                        lock_reason = f"Waiting for '{previous_task.title}' to be graded"
                    else:
                        percentage = (previous_submission.marks_obtained / previous_task.max_marks) * 100
                        if percentage < 70:
                            is_locked = True
                            lock_reason = f"You need to score at least 70% in '{previous_task.title}' to unlock this task. Current score: {percentage:.1f}%"
            except ValueError:
                pass
            
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
                'is_locked': is_locked,
                'lock_reason': lock_reason,
                'is_submitted': submission is not None,
                'submission': {
                    'id': submission.id,
                    'submitted_at': submission.submitted_at,
                    'submission_text': submission.submission_text,
                    'submission_file': request.build_absolute_uri(submission.submission_file.url) if submission.submission_file else None,
                    'marks_obtained': submission.marks_obtained,
                    'feedback': submission.feedback,
                } if submission else None,
            }
            
            return Response(task_data)
            
        except Task.DoesNotExist:
            return Response(
                {'error': 'Task not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class StudentSubmitTaskView(APIView):
    """View for students to submit tasks"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            if request.user.role != 'student':
                return Response(
                    {'error': 'Only students can submit tasks'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            task_id = request.data.get('task_id')
            submission_text = request.data.get('submission_text', '')
            submission_file = request.FILES.get('submission_file')
            
            if not task_id:
                return Response(
                    {'error': 'task_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not submission_text and not submission_file:
                return Response(
                    {'error': 'Please provide either submission text or a file'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            task = Task.objects.get(id=task_id)
            
            if not task.assigned_to.filter(id=request.user.id).exists():
                return Response(
                    {'error': 'You are not assigned to this task'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
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
            )
            
            # ✅ SEND NOTIFICATION (if notifications app exists)
            try:
                from notifications.utils import notify_on_task_submission
                print(f"\n🔔 CALLING NOTIFICATION FUNCTION")
                print(f"   Task: {task.title}")
                print(f"   Student: {request.user.username}")
                
                notify_on_task_submission(task, request.user, submission)
                
                print(f"🔔 NOTIFICATION FUNCTION COMPLETED\n")
            except ImportError:
                print("⚠️ Notifications app not found, skipping notifications")
            except Exception as e:
                print(f"⚠️ Notification error: {str(e)}")
            
            return Response({
                'message': 'Task submitted successfully',
                'submission_id': submission.id,
            }, status=status.HTTP_201_CREATED)
            
        except Task.DoesNotExist:
            return Response(
                {'error': 'Task not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
