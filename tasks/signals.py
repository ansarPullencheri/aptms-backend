from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from courses.models import Batch
from tasks.models import Task


@receiver(m2m_changed, sender=Batch.students.through)
def assign_existing_tasks_to_new_student(sender, instance, action, pk_set, **kwargs):
  
    if action == "post_add":
        batch = instance
        
        from authentication.models import User
        new_students = User.objects.filter(
            id__in=pk_set, 
            role='student', 
            is_approved=True
        )
        
        if new_students.exists():
          
            batch_tasks = Task.objects.filter(batch=batch)
            
           
            course_tasks = Task.objects.filter(
                course=batch.course, 
                task_type='course'
            )
            
            all_tasks = batch_tasks | course_tasks
            
           
            for task in all_tasks.distinct():
                for student in new_students:
                    task.assigned_to.add(student)
      
            if all_tasks.exists():
                print(f"✅ AUTO-ASSIGNED {all_tasks.count()} tasks to {new_students.count()} new student(s) in batch '{batch.name}'")
