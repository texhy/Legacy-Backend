"""
Celery configuration for Legacy app.

This handles all asynchronous background tasks:
- Knowledge extraction
- Memory compression
- Life narrative updates
- Session primer updates
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Create Celery app
app = Celery('legacy')

# Load config from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Celery Beat Schedule (Periodic Tasks)
app.conf.beat_schedule = {
    # Run life narrative update every night at 3 AM
    'update-life-narratives-nightly': {
        'task': 'apps.ai.tasks.update_all_life_narratives',
        'schedule': crontab(hour=3, minute=0),
    },
    
    # Clean up old compressed messages every week (Sunday 4 AM)
    'cleanup-old-messages-weekly': {
        'task': 'apps.ai.tasks.cleanup_compressed_messages',
        'schedule': crontab(hour=4, minute=0, day_of_week=0),
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
