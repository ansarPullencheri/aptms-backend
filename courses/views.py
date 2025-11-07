from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser  
from django.db.models import Q, Prefetch
from .models import Course, Batch
from .serializers import CourseSerializer, BatchSerializer, BatchDetailSerializer
from authentication.models import User
from authentication.permissions import IsAdmin, IsMentor, IsAdminOrMentor
from tasks.models import Task, TaskSubmission
from django.http import FileResponse, Http404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
import os


# Course Views
class CourseListView(generics.ListAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated]


class CourseDetailView(generics.RetrieveAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated]


class CourseCreateView(generics.CreateAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)  
    
    def perform_create(self, serializer):
        if self.request.user.role != 'admin':
            raise permissions.PermissionDenied("Only admins can create courses")
        serializer.save(created_by=self.request.user)


class CourseUpdateView(generics.UpdateAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser) 
    
    def perform_update(self, serializer):
        if self.request.user.role != 'admin':
            raise permissions.PermissionDenied("Only admins can update courses")
        serializer.save()


class CourseDeleteView(generics.DestroyAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_destroy(self, instance):
        if self.request.user.role != 'admin':
            raise permissions.PermissionDenied("Only admins can delete courses")
        
        # Delete syllabus file if exists
        if instance.syllabus:
            if os.path.isfile(instance.syllabus.path):
                os.remove(instance.syllabus.path)
        
        instance.delete()


class AssignMentorView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        if request.user.role != 'admin':
            return Response(
                {"error": "Only admins can assign mentors"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            course = Course.objects.get(pk=pk)
            mentor_id = request.data.get('mentor_id')
            
            if mentor_id:
                mentor = User.objects.get(id=mentor_id, role='mentor')
                course.mentor = mentor
                course.save()
                return Response(
                    {"message": "Mentor assigned successfully"},
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {"error": "Mentor ID is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Course.DoesNotExist:
            return Response(
                {"error": "Course not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except User.DoesNotExist:
            return Response(
                {"error": "Mentor not found"},
                status=status.HTTP_404_NOT_FOUND
            )


#  Download Syllabus View
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_syllabus(request, pk):
    """
    Download syllabus PDF for a course
    """
    try:
        course = Course.objects.get(id=pk)
        
        # Check if syllabus file exists
        if not course.syllabus:
            return Response({
                'error': 'Syllabus not available for this course'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get the file path
        file_path = course.syllabus.path
        
        if not os.path.exists(file_path):
            return Response({
                'error': 'Syllabus file not found on server'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Serve the file
        response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{course.name}_Syllabus.pdf"'
        
        return response
        
    except Course.DoesNotExist:
        return Response({
            'error': 'Course not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Batch Views
class BatchListView(generics.ListAPIView):
    queryset = Batch.objects.all()
    serializer_class = BatchSerializer
    permission_classes = [permissions.IsAuthenticated]


class BatchDetailView(generics.RetrieveAPIView):
    queryset = Batch.objects.all()
    serializer_class = BatchSerializer
    permission_classes = [permissions.IsAuthenticated]


class BatchCreateView(generics.CreateAPIView):
    queryset = Batch.objects.all()
    serializer_class = BatchSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        if self.request.user.role != 'admin':
            raise permissions.PermissionDenied("Only admins can create batches")
        serializer.save()


class BatchUpdateView(generics.UpdateAPIView):
    queryset = Batch.objects.all()
    serializer_class = BatchSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_update(self, serializer):
        if self.request.user.role != 'admin':
            raise permissions.PermissionDenied("Only admins can update batches")
        serializer.save()


class BatchDeleteView(generics.DestroyAPIView):
    queryset = Batch.objects.all()
    serializer_class = BatchSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_destroy(self, instance):
        if self.request.user.role != 'admin':
            raise permissions.PermissionDenied("Only admins can delete batches")
        instance.delete()


class AddStudentsToBatchView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        if request.user.role != 'admin':
            return Response(
                {"error": "Only admins can add students to batches"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            batch = Batch.objects.get(pk=pk)
            student_ids = request.data.get('student_ids', [])
            
            for student_id in student_ids:
                student = User.objects.get(id=student_id, role='student', is_approved=True)
                batch.students.add(student)
            
            return Response(
                {"message": f"{len(student_ids)} student(s) added to batch"},
                status=status.HTTP_200_OK
            )
        except Batch.DoesNotExist:
            return Response(
                {"error": "Batch not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except User.DoesNotExist:
            return Response(
                {"error": "One or more students not found or not approved"},
                status=status.HTTP_404_NOT_FOUND
            )


# Mentor-Specific Views
class MentorAssignedBatchesView(generics.ListAPIView):
    serializer_class = BatchDetailSerializer
    permission_classes = [permissions.IsAuthenticated, IsMentor]
    
    def get_queryset(self):
        return Batch.objects.filter(
            mentor=self.request.user
        ).prefetch_related(
            'students',
            'students__student_profile',
            'course'
        ).order_by('-created_at')


class MentorBatchDetailView(generics.RetrieveAPIView):
    serializer_class = BatchDetailSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrMentor]
    
    def get_queryset(self):
        if self.request.user.role == 'admin':
            return Batch.objects.all()
        return Batch.objects.filter(mentor=self.request.user)


class BatchStudentsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrMentor]
    
    def get(self, request, batch_id):
        try:
            if request.user.role == 'admin':
                batch = Batch.objects.get(id=batch_id)
            else:
                batch = Batch.objects.get(id=batch_id, mentor=request.user)
            
            students = batch.students.all().select_related('student_profile')
            
            students_data = []
            for student in students:
                student_info = {
                    'id': student.id,
                    'username': student.username,
                    'email': student.email,
                    'first_name': student.first_name,
                    'last_name': student.last_name,
                    'phone': student.phone,
                    'is_approved': student.is_approved,
                    'profile_picture': request.build_absolute_uri(student.profile_picture.url) if student.profile_picture else None,
                }
                
                if hasattr(student, 'student_profile'):
                    student_info.update({
                        'enrollment_number': student.student_profile.enrollment_number,
                        'date_of_birth': student.student_profile.date_of_birth,
                        'address': student.student_profile.address,
                    })
                
                assigned_tasks = Task.objects.filter(
                    batch=batch,
                    assigned_to=student
                )
                submitted_tasks = TaskSubmission.objects.filter(
                    task__batch=batch,
                    student=student
                )
                
                student_info.update({
                    'total_assigned_tasks': assigned_tasks.count(),
                    'submitted_tasks': submitted_tasks.count(),
                    'pending_tasks': assigned_tasks.count() - submitted_tasks.count(),
                })
                
                students_data.append(student_info)
            
            return Response({
                'batch_id': batch.id,
                'batch_name': batch.name,
                'course_name': batch.course.name,
                'total_students': len(students_data),
                'students': students_data
            })
            
        except Batch.DoesNotExist:
            return Response(
                {'error': 'Batch not found or you do not have access'},
                status=status.HTTP_404_NOT_FOUND
            )


class StudentDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrMentor]
    
    def get(self, request, student_id):
        try:
            student = User.objects.select_related('student_profile').get(
                id=student_id,
                role='student',
                is_approved=True
            )
            
            if request.user.role == 'mentor':
                has_access = Batch.objects.filter(
                    mentor=request.user,
                    students=student
                ).exists()
                
                if not has_access:
                    return Response(
                        {'error': 'You do not have access to this student'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            enrolled_batches = student.enrolled_batches.select_related('course', 'mentor')
            assigned_tasks = Task.objects.filter(assigned_to=student)
            submissions = TaskSubmission.objects.filter(student=student)
            
            student_data = {
                'id': student.id,
                'username': student.username,
                'email': student.email,
                'first_name': student.first_name,
                'last_name': student.last_name,
                'phone': student.phone,
                'profile_picture': request.build_absolute_uri(student.profile_picture.url) if student.profile_picture else None,
                'created_at': student.created_at,
            }
            
            if hasattr(student, 'student_profile'):
                student_data.update({
                    'enrollment_number': student.student_profile.enrollment_number,
                    'date_of_birth': student.student_profile.date_of_birth,
                    'address': student.student_profile.address,
                })
            
            student_data.update({
                'enrolled_batches': [
                    {
                        'id': batch.id,
                        'name': batch.name,
                        'course_name': batch.course.name,
                        'mentor_name': f"{batch.mentor.first_name} {batch.mentor.last_name}" if batch.mentor else None,
                    }
                    for batch in enrolled_batches
                ],
                'task_statistics': {
                    'total_assigned': assigned_tasks.count(),
                    'total_submitted': submissions.count(),
                    'pending': assigned_tasks.count() - submissions.count(),
                    'graded': submissions.filter(marks_obtained__isnull=False).count(),
                }
            })
            
            return Response(student_data)
            
        except User.DoesNotExist:
            return Response(
                {'error': 'Student not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class StudentSubmissionsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrMentor]
    
    def get(self, request, student_id):
        try:
            student = User.objects.get(id=student_id, role='student')
            
            if request.user.role == 'mentor':
                has_access = Batch.objects.filter(
                    mentor=request.user,
                    students=student
                ).exists()
                
                if not has_access:
                    return Response(
                        {'error': 'You do not have access to this student'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            submissions = TaskSubmission.objects.filter(
                student=student
            ).select_related('task', 'task__course').order_by('-submitted_at')
            
            submissions_data = []
            for submission in submissions:
                submissions_data.append({
                    'id': submission.id,
                    'task_title': submission.task.title,
                    'task_id': submission.task.id,
                    'course_name': submission.task.course.name if submission.task.course else 'N/A',
                    'submitted_at': submission.submitted_at,
                    'status': submission.status,
                    'marks_obtained': submission.marks_obtained,
                    'max_marks': submission.task.max_marks,
                    'feedback': submission.feedback,
                    'submission_file': request.build_absolute_uri(submission.submission_file.url) if submission.submission_file else None,
                })
            
            return Response({
                'student': {
                    'id': student.id,
                    'username': student.username,
                    'first_name': student.first_name,
                    'last_name': student.last_name,
                    'email': student.email,
                },
                'submissions': submissions_data,
                'total_submissions': len(submissions_data),
            })
            
        except User.DoesNotExist:
            return Response(
                {'error': 'Student not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class StudentBatchesView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, student_id):
        try:
            student = User.objects.get(id=student_id, role='student')
            
            if request.user.role == 'mentor':
                has_access = Batch.objects.filter(
                    mentor=request.user,
                    students=student
                ).exists()
                
                if not has_access:
                    return Response(
                        {'error': 'You do not have access to this student'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            elif request.user.role not in ['admin', 'mentor']:
                if request.user.id != student_id:
                    return Response(
                        {'error': 'You do not have permission to view this data'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            enrolled_batches = Batch.objects.filter(
                students=student
            ).select_related('course', 'mentor').prefetch_related('students')
            
            batches_data = []
            for batch in enrolled_batches:
                batch_info = {
                    'id': batch.id,
                    'name': batch.name,
                    'course': {
                        'id': batch.course.id,
                        'name': batch.course.name,
                        'code': batch.course.code,
                    },
                    'mentor': {
                        'id': batch.mentor.id,
                        'name': f"{batch.mentor.first_name} {batch.mentor.last_name}",
                        'email': batch.mentor.email,
                    } if batch.mentor else None,
                    'student_count': batch.students.filter(is_approved=True).count(),
                    'start_date': batch.start_date,
                    'end_date': batch.end_date,
                }
                batches_data.append(batch_info)
            
            total_tasks = Task.objects.filter(assigned_to=student).count()
            total_submissions = TaskSubmission.objects.filter(student=student).count()
            
            return Response({
                'student': {
                    'id': student.id,
                    'username': student.username,
                    'first_name': student.first_name,
                    'last_name': student.last_name,
                    'email': student.email,
                },
                'batches': batches_data,
                'total_batches': len(batches_data),
                'task_statistics': {
                    'total_tasks': total_tasks,
                    'total_submissions': total_submissions,
                    'pending_tasks': total_tasks - total_submissions,
                }
            })
            
        except User.DoesNotExist:
            return Response(
                {'error': 'Student not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
