from rest_framework import generics, status, permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .models import User, StudentProfile, MentorProfile
from .serializers import StudentRegistrationSerializer, UserSerializer
from .permissions import IsAdmin


class StudentRegistrationView(generics.CreateAPIView):
    serializer_class = StudentRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            
            return Response({
                "message": "Registration successful! Please wait for admin approval.",
                "user": UserSerializer(user).data
            }, status=status.HTTP_201_CREATED)
            
        except serializers.ValidationError as e:
            return Response(
                e.detail,
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response(
                {"error": "Username and password are required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = authenticate(username=username, password=password)
        
        if user is None:
            return Response(
                {"error": "Invalid credentials"}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.is_active:
            return Response(
                {"error": "Your account has been deactivated"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        if user.role == 'student' and not user.is_approved and not user.is_superuser:
            return Response(
                {"error": "Your account is pending admin approval"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        refresh = RefreshToken.for_user(user)
        
        return Response({
            "message": "Login successful",
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": UserSerializer(user).data
        }, status=status.HTTP_200_OK)


class PendingStudentsView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.role != 'admin':
            return User.objects.none()
        return User.objects.filter(role='student', is_approved=False).order_by('-created_at')


class ApproveStudentView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, user_id):
        print(f"Approve request received for user_id: {user_id}")
        print(f"Request user: {request.user.username}, role: {request.user.role}")
        print(f"Batch IDs: {request.data.get('batch_ids', [])}")
        
        if request.user.role != 'admin':
            return Response(
                {"error": "Only admins can approve students"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            student = User.objects.get(id=user_id, role='student')
            print(f"Student found: {student.username}, current approval: {student.is_approved}")
            
            batch_ids = request.data.get('batch_ids', [])
            
            student.is_approved = True
            student.save()
            
            print(f"Student {student.username} approved: {student.is_approved}")
            
            assigned_count = 0
            if batch_ids:
                from courses.models import Batch
                batches = Batch.objects.filter(id__in=batch_ids)
                print(f"Batches found: {batches.count()}")
                for batch in batches:
                    batch.students.add(student)
                    assigned_count += 1
                    print(f"Added to batch: {batch.name}")
            
            return Response({
                "message": f"Student {student.username} approved successfully",
                "student": UserSerializer(student).data,
                "assigned_batches": assigned_count
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            print(f"Student with id {user_id} not found")
            return Response(
                {"error": "Student not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"Error approving student: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class UserListView(generics.ListAPIView):
    """View for admins to see all users."""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    
    def get_queryset(self):
        role = self.request.query_params.get('role', None)
        if role:
            return User.objects.filter(role=role)
        return User.objects.all()


class MentorListView(generics.ListAPIView):
    """View to list all mentors."""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    
    def get_queryset(self):
        return User.objects.filter(role='mentor')


class StudentListView(generics.ListAPIView):
    """View to list all approved students."""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    
    def get_queryset(self):
        return User.objects.filter(role='student', is_approved=True)


class CreateMentorView(generics.CreateAPIView):
    """View for admins to create mentor accounts."""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    
    def create(self, request, *args, **kwargs):
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')
        phone = request.data.get('phone', '')
        
        if not username or not email or not password:
            return Response(
                {"error": "Username, email, and password are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            mentor = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                role='mentor',
                is_approved=True
            )
            
            MentorProfile.objects.create(
                user=mentor,
                specialization=request.data.get('specialization', ''),
                experience_years=request.data.get('experience_years', 0),
                bio=request.data.get('bio', '')
            )
            
            return Response(
                {
                    "message": "Mentor created successfully",
                    "user": UserSerializer(mentor).data
                },
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """View for admins to get, update, or delete a specific user."""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response({
            "message": "User updated successfully",
            "user": serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        username = instance.username
        self.perform_destroy(instance)
        return Response(
            {"message": f"User '{username}' deleted successfully"},
            status=status.HTTP_200_OK
        )


class AdminResetPasswordView(APIView):
    """
    Admin can reset any user's password
    Perfect for when students use dummy emails
    """
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    
    def post(self, request):
        try:
            user_id = request.data.get('user_id')
            new_password = request.data.get('new_password')
            
            if not user_id or not new_password:
                return Response({
                    'error': 'user_id and new_password are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user = User.objects.get(id=user_id)
            
            user.set_password(new_password)
            user.save()
            
            return Response({
                'success': True,
                'message': f'Password reset successful for {user.username}',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'name': f"{user.first_name} {user.last_name}"
                }
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class AdminGeneratePasswordView(APIView):
    """
    Generate a random secure password for a user
    """
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    
    def post(self, request):
        try:
            import random
            import string
            
            user_id = request.data.get('user_id')
            
            if not user_id:
                return Response({
                    'error': 'user_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user = User.objects.get(id=user_id)
            
            characters = string.ascii_letters + string.digits
            new_password = ''.join(random.choice(characters) for i in range(8))
            
            user.set_password(new_password)
            user.save()
            
            return Response({
                'success': True,
                'message': f'Password generated for {user.username}',
                'new_password': new_password,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'name': f"{user.first_name} {user.last_name}"
                }
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


# ✅ Student Dashboard View
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def student_dashboard(request):
    """
    Get student dashboard data with all relevant information
    """
    try:
        student = request.user
        
        if student.role != 'student':
            return Response({
                'error': 'Only students can access this endpoint'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get enrolled batches with course_id
        enrolled_batches = []
        for batch in student.enrolled_batches.all():
            enrolled_batches.append({
                'id': batch.id,
                'name': batch.name,
                'course_id': batch.course.id,  # ✅ Include course_id
                'course_name': batch.course.name,
                'mentor_name': f"{batch.mentor.first_name} {batch.mentor.last_name}" if batch.mentor else None,
            })
        
        # Get task statistics
        from tasks.models import Task, TaskSubmission
        
        assigned_tasks = Task.objects.filter(assigned_to=student)
        submitted_tasks = TaskSubmission.objects.filter(student=student)
        
        task_statistics = {
            'total_assigned': assigned_tasks.count(),
            'total_submitted': submitted_tasks.count(),
            'pending_tasks': assigned_tasks.count() - submitted_tasks.count(),
        }
        
        # Get recent submissions
        recent_submissions = []
        for submission in submitted_tasks.order_by('-submitted_at')[:5]:
            recent_submissions.append({
                'task_title': submission.task.title,
                'submitted_at': submission.submitted_at,
                'is_graded': submission.marks_obtained is not None,
                'marks_obtained': submission.marks_obtained,
                'max_marks': submission.task.max_marks,
            })
        
        # Calculate academic progress
        graded_submissions = submitted_tasks.filter(marks_obtained__isnull=False)
        if graded_submissions.exists():
            total_marks = sum(s.task.max_marks for s in graded_submissions)
            obtained_marks = sum(s.marks_obtained for s in graded_submissions)
            overall_percentage = round((obtained_marks / total_marks * 100), 2) if total_marks > 0 else 0
        else:
            overall_percentage = 0
        
        academic_progress = {
            'overall_percentage': overall_percentage,
        }
        
        # Student info
        student_info = {
            'name': f"{student.first_name} {student.last_name}",
            'username': student.username,
            'email': student.email,
        }
        
        return Response({
            'student_info': student_info,
            'enrolled_batches': enrolled_batches,
            'task_statistics': task_statistics,
            'recent_submissions': recent_submissions,
            'academic_progress': academic_progress,
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
