from celery.schedules import crontab

# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Celery Beat Schedule
CELERY_BEAT_SCHEDULE = {
    'check-approaching-deadlines': {
        'task': 'communications.tasks.check_approaching_deadlines',
        'schedule': crontab(hour=9, minute=0),  # Her gün saat 09:00'da çalışır
    },
} 