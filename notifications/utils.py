from .models import Notification
from django.contrib.auth import get_user_model



import os
import gspread
from google.oauth2.service_account import Credentials
from django.conf import settings

import gspread
from django.conf import settings
# from .utils import get_google_credentials 



from django.core.mail import send_mail

import time

from django.utils import timezone


User = get_user_model()

def create_notification(recipients, sender, notification_type, title, message, link=None):
    """Create notifications for multiple recipients"""
    notifications = []
    unique_recipients = list(set(recipients))
    
    for recipient in unique_recipients:
        if recipient == sender:
            continue
            
        notif = Notification.objects.create(
            recipient=recipient,
            sender=sender,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link
        )
        notifications.append(notif)
    
    print(f" Created {len(notifications)} notifications for {notification_type}")
    return notifications


def notify_on_task_submission(task, student, submission):
    """Notify mentor and admin when student submits a task"""
    recipients = []
    
    print(f"\n{'='*60}")
    print(f"📩 NOTIFY ON TASK SUBMISSION CALLED")
    print(f"{'='*60}")
    print(f"Task: {task.title} (ID: {task.id})")
    print(f"Student: {student.username} ({student.first_name} {student.last_name})")
    print(f"Batch: {task.batch}")
    
    # Get mentor from batch
    if task.batch and task.batch.mentor:
        recipients.append(task.batch.mentor)
        print(f" Added mentor: {task.batch.mentor.username}")
    else:
        print(f" No mentor found for batch: {task.batch}")
        # For course-wide tasks, get all mentors of course batches
        if task.course:
            from courses.models import Batch
            course_batches = Batch.objects.filter(course=task.course)
            for batch in course_batches:
                if batch.mentor:
                    recipients.append(batch.mentor)
                    print(f" Added mentor from {batch.name}: {batch.mentor.username}")
    
    # Get all admins
    admins = User.objects.filter(role='admin')
    recipients.extend(admins)
    print(f" Added {admins.count()} admin(s)")
    for admin in admins:
        print(f"   - {admin.username}")
    
    if not recipients:
        print(f"❌ ERROR: No recipients found!")
        print(f"{'='*60}\n")
        return []
    
    print(f"\n Total unique recipients: {len(set(recipients))}")
    
    link = f"/mentor/grade-submissions/{task.batch.id}" if task.batch else "/admin/tasks"
    
    result = create_notification(
        recipients=recipients,
        sender=student,
        notification_type='task_submitted',
        title="New Task Submission",
        message=f"{student.first_name} {student.last_name} submitted '{task.title}'",
        link=link
    )
    
    print(f"{'='*60}\n")
    return result


def notify_on_task_graded(submission, grader):
    """Notify student when task is graded"""
    print(f" Task graded notification for {submission.student.username}")
    return create_notification(
        recipients=[submission.student],
        sender=grader,
        notification_type='task_graded',
        title=f"Task Graded: {submission.task.title}",
        message=f"You received {submission.marks_obtained}/{submission.task.max_marks} marks",
        link="/student/submissions"
    )


def notify_on_task_created(task, creator):
    """Notify students when new task is created"""
    recipients = list(task.assigned_to.filter(is_approved=True))
    
    print(f"Task created notification - {task.title}")
    print(f"   Assigned to {len(recipients)} students")
    
    # If mentor creates task, notify admin
    if creator.role == 'mentor':
        recipients.extend(User.objects.filter(role='admin'))
    
    # If admin creates task, notify mentor
    if creator.role == 'admin' and task.batch and task.batch.mentor:
        recipients.append(task.batch.mentor)
    
    return create_notification(
        recipients=recipients,
        sender=creator,
        notification_type='task_created',
        title="New Task Assigned",
        message=f"New task '{task.title}' has been assigned",
        link=f"/student/tasks/{task.id}"
    )





# ============google sheet integration===============



import os, json, base64
from google.oauth2.service_account import Credentials

def get_google_credentials():
    """Load Google credentials from BASE64 environment variable"""
    data = os.getenv("GOOGLE_SHEET_CREDENTIALS_BASE64")
    if not data:
        raise ValueError("GOOGLE_SHEET_CREDENTIALS_BASE64 not found in environment.")

    creds_dict = json.loads(base64.b64decode(data))
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    return creds
        




def export_student_to_google_sheet(user):
    """Export a single newly registered student (with photo) to Google Sheet"""

    try:
        #  Load credentials from BASE64 (no JSON file needed)
        creds = get_google_credentials()

        #  Authorize client
        client = gspread.authorize(creds)

        #  Open Google Sheet
        sheet = client.open("Tefora_Registrations").sheet1

        #  Add headers if sheet is empty
        if not sheet.get_all_values():
            headers = [
                "First Name", "Last Name", "Email", "Phone", "Gender",
                "Date of Birth", "Blood Group", "Address",
                "Guardian Name", "Guardian Phone", "Photo"
            ]
            sheet.append_row(headers)

        #  Safe text helper
        def safe(value):
            return str(value).strip() if value else ""

        #  Get student profile
        profile = getattr(user, "student_profile", None)

        #  Get photo URL (if uploaded)
        photo_url = ""
        if profile and getattr(profile, "photo", None):
            request = getattr(user, "_request", None)
            if request:
                photo_url = request.build_absolute_uri(profile.photo.url)
            else:
                photo_url = f"{settings.MEDIA_URL}{profile.photo.url}"

        #  Append data row
        sheet.append_row([
            safe(user.first_name),
            safe(user.last_name),
            safe(user.email),
            safe(getattr(user, "phone", "")),
            safe(profile.gender if profile else ""),
            profile.date_of_birth.strftime("%Y-%m-%d") if profile and profile.date_of_birth else "",
            safe(profile.blood_group if profile else ""),
            safe(profile.address if profile else ""),
            safe(profile.guardian_name if profile else ""),
            safe(profile.guardian_phone if profile else ""),
            f'=IMAGE("{photo_url}")' if photo_url else ""
        ])

        print(f" Exported {user.email} (with photo) to Google Sheet successfully.")

    except Exception as e:
        print(f" Google Sheet export failed: {e}")






# -----------email notifications ----------

# User = get_user_model()

# def send_email_on_task_submission(task, student, submission):
#     """Send email notification to the appropriate mentor when a student submits a task."""
#     try:
#         print(f"DEBUG: Preparing to send email for task {task.id} - {task.title}")

#         #  Choose mentor based on task type
#         mentor = None
#         if task.task_type == 'course' and hasattr(task.course, 'mentor'):
#             mentor = task.course.mentor
#             print(f"DEBUG: Mentor selected from course = {mentor}")
#         elif task.task_type == 'batch' and hasattr(task.batch, 'mentor'):
#             mentor = task.batch.mentor
#             print(f"DEBUG: Mentor selected from batch = {mentor}")
#         else:
#             print("No valid mentor relation found for this task.")
#             return

#         #  Validate mentor email
#         if not mentor or not getattr(mentor, 'email', None):
#             print("No mentor email found for this task submission.")
#             return

#         #  Build email
#         subject = f"New Task Submission: {task.title}"
#         message = (
#             f"Hello {mentor.get_full_name() or mentor.username},\n\n"
#             f"Student {student.get_full_name() or student.username} "
#             f"has submitted the task '{task.title}'.\n\n"
#             f"Course: {task.course.name if task.course else 'N/A'}\n"
#             f"Batch: {task.batch.name if task.batch else 'N/A'}\n"
#             f"Submitted At: {submission.submitted_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
#             f"Please log in to review the submission.\n\n"
#             f"Best regards,\n"
#             f"Tefora Management System"
#         )

#         #  Send email
#         send_mail(
#             subject,
#             message,
#             settings.DEFAULT_FROM_EMAIL,
#             [mentor.email],
#             fail_silently=False,
#         )

#         print(f" Email sent to mentor: {mentor.email}")

#     except Exception as e:
#         import traceback
#         print(f"Failed to send mentor email: {e}")
#         print(traceback.format_exc())

        

# def send_email_on_task_graded(submission):
#     """Send email to student when mentor grades their task."""
#     student = submission.student
#     task = submission.task

#     if not student.email:
#         print(f" No email found for student {student.username}")
#         return

#     marks = submission.marks_obtained if submission.marks_obtained is not None else "Not specified"
#     feedback = submission.feedback if submission.feedback else "No feedback provided"

#     #  Conditional message based on marks
#     if isinstance(marks, (int, float)) and marks >= 70:
#         extra_message = (
#             "\n Congratulations! Your next task has been unlocked.\n"
#             "You can now access it from your dashboard.\n"
#         )
#     elif isinstance(marks, (int, float)):
#         extra_message = (
#             "\n Your marks did not meet the required level to unlock the next week's task.\n"
#             "try to improve in the next submission.\n"
#         )
#     else:
#         extra_message = ""

#     subject = f"Task Graded: {task.title}"
#     message = (
#         f"Hello {student.get_full_name() or student.username},\n\n"
#         f"Your task '{task.title}' has been graded by your mentor.\n\n"
#         f"Marks: {marks}\n"
#         f"Feedback: {feedback}\n"
#         f"{extra_message}\n"
#         f"Best regards,\n"
#         f"Tefora Management System"
#     )

#     send_mail(
#         subject,
#         message,
#         settings.DEFAULT_FROM_EMAIL,
#         [student.email],
#         fail_silently=False,
#     )

#     print(f" Grade email sent to {student.email} with marks {marks}")
