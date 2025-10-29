from .models import Notification
from django.contrib.auth import get_user_model

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
    
    print(f"✅ Created {len(notifications)} notifications for {notification_type}")
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
        print(f"✅ Added mentor: {task.batch.mentor.username}")
    else:
        print(f"⚠️ No mentor found for batch: {task.batch}")
        # For course-wide tasks, get all mentors of course batches
        if task.course:
            from courses.models import Batch
            course_batches = Batch.objects.filter(course=task.course)
            for batch in course_batches:
                if batch.mentor:
                    recipients.append(batch.mentor)
                    print(f"✅ Added mentor from {batch.name}: {batch.mentor.username}")
    
    # Get all admins
    admins = User.objects.filter(role='admin')
    recipients.extend(admins)
    print(f"✅ Added {admins.count()} admin(s)")
    for admin in admins:
        print(f"   - {admin.username}")
    
    if not recipients:
        print(f"❌ ERROR: No recipients found!")
        print(f"{'='*60}\n")
        return []
    
    print(f"\n📧 Total unique recipients: {len(set(recipients))}")
    
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
    print(f"📩 Task graded notification for {submission.student.username}")
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
    
    print(f"📩 Task created notification - {task.title}")
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
