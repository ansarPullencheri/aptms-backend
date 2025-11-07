from rest_framework import serializers
from .models import User, StudentProfile, MentorProfile
from django.contrib.auth.password_validation import validate_password



# ---------forgot and reset--------------

from django.contrib.auth import get_user_model
from django.utils.encoding import smart_str, force_bytes, DjangoUnicodeDecodeError
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.auth.tokens import PasswordResetTokenGenerator



class UserSerializer(serializers.ModelSerializer):
    student_profile = serializers.SerializerMethodField()
    profile_picture = serializers.ImageField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'phone', 'profile_picture', 'is_approved', 'is_active', 'created_at',
            'student_profile'
        ]
        read_only_fields = ['id', 'is_approved', 'created_at']

    def get_student_profile(self, obj):
        """Return student-specific details if the user has a StudentProfile."""
        if hasattr(obj, 'student_profile'):
            profile = obj.student_profile
            return {
                'gender': profile.gender,
                'date_of_birth': profile.date_of_birth,
                'blood_group': profile.blood_group,
                'address': profile.address,
                'guardian_name': profile.guardian_name,
                'guardian_phone': profile.guardian_phone,
                'enrollment_number': profile.enrollment_number,
            }
        return None

# class UserSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = User
#         fields = ['id', 'username', 'email', 'first_name', 'last_name', 
#                  'role', 'phone', 'is_approved', 'is_active', 'created_at']
#         read_only_fields = ['id', 'is_approved', 'created_at']


# class StudentRegistrationSerializer(serializers.ModelSerializer):
#     password = serializers.CharField(
#         write_only=True, 
#         required=True, 
#         validators=[validate_password],
#         style={'input_type': 'password'}
#     )
#     password2 = serializers.CharField(
#         write_only=True, 
#         required=True,
#         style={'input_type': 'password'}
#     )
    
#     class Meta:
#         model = User
#         fields = ['username', 'email', 'first_name', 'last_name', 
#                  'phone', 'password', 'password2']
    
#     def validate(self, attrs):
#         if attrs['password'] != attrs['password2']:
#             raise serializers.ValidationError({"password": "Password fields didn't match."})
        
#         # Validate email uniqueness
#         if User.objects.filter(email=attrs['email']).exists():
#             raise serializers.ValidationError({"email": "This email is already registered."})
        
#         # Validate username uniqueness
#         if User.objects.filter(username=attrs['username']).exists():
#             raise serializers.ValidationError({"username": "This username is already taken."})
        
#         return attrs
    
#     def create(self, validated_data):
#         # Remove password2 before creating user
#         validated_data.pop('password2')
        
#         # create_user() automatically hashes the password
#         user = User.objects.create_user(
#             username=validated_data['username'],
#             email=validated_data['email'],
#             password=validated_data['password'],
#             first_name=validated_data['first_name'],
#             last_name=validated_data['last_name'],
#             phone=validated_data.get('phone', ''),
#             role='student',
#             is_approved=False
#         )
        
#         # Create student profile
#         StudentProfile.objects.create(user=user)
        
#         return user


class StudentRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password2 = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'phone', 'password', 'password2', 'profile_picture'
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})

        if User.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError({"email": "This email is already registered."})
        if User.objects.filter(username=attrs['username']).exists():
            raise serializers.ValidationError({"username": "This username is already taken."})

        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        validated_data.pop('password2', None)

        #  Collect both flat and nested student_profile data
        profile_data = {}

        #  If frontend sends nested keys like "student_profile.gender"
        for key, value in self.initial_data.items():
            if key.startswith("student_profile."):
                field_name = key.replace("student_profile.", "")
                profile_data[field_name] = value

        # 2️ If frontend sends flat fields (like gender, address, etc.)
        for field in [
            'gender', 'date_of_birth', 'blood_group', 'address',
            'guardian_name', 'guardian_phone', 'photo', 'enrollment_number'
        ]:
            if field not in profile_data and field in self.initial_data:
                profile_data[field] = self.initial_data.get(field)

        #  Create the user
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=password,
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            phone=validated_data.get('phone', ''),
            profile_picture=validated_data.get('profile_picture', None),
            role='student',
            is_approved=False
        )

        #  Create associated student profile
        StudentProfile.objects.create(
            user=user,
            gender=profile_data.get('gender'),
            date_of_birth=self.parse_date(profile_data.get('date_of_birth')),
            blood_group=profile_data.get('blood_group'),
            address=profile_data.get('address'),
            guardian_name=profile_data.get('guardian_name'),
            guardian_phone=profile_data.get('guardian_phone'),
            photo=profile_data.get('photo'),
            enrollment_number=profile_data.get('enrollment_number')
        )

        return user

    def parse_date(self, value):
        """Helper to safely parse date strings."""
        from datetime import datetime
        if value:
            try:
                return datetime.strptime(value, "%Y-%m-%d").date()
            except Exception:
                return None
        return None

class StudentProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = StudentProfile
        fields = '__all__'


class MentorProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = MentorProfile
        fields = '__all__'






# ------forgot and  reset password serializers--------------



User = get_user_model()

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email does not exist.")
        return value


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    uidb64 = serializers.CharField()
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    def validate(self, attrs):
        password = attrs.get('password')
        password2 = attrs.get('password2')
        token = attrs.get('token')
        uidb64 = attrs.get('uidb64')

        if password != password2:
            raise serializers.ValidationError("Passwords do not match.")

        try:
            uid = smart_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(id=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist, DjangoUnicodeDecodeError):
            raise serializers.ValidationError("Invalid token or user ID.")

        if not PasswordResetTokenGenerator().check_token(user, token):
            raise serializers.ValidationError("Token is invalid or expired.")

        user.set_password(password)
        user.save()
        return attrs
