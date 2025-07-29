from celery import Celery
from app import create_app
from app.services.email_service import send_async_email
from app.services.notification_service import notification_service
from datetime import datetime, timedelta

def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    celery.conf.update(app.config)
    
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery

# Create Flask app and Celery instance
flask_app = create_app()
celery = make_celery(flask_app)

# Periodic tasks
@celery.task
def send_booking_reminders():
    """Send booking reminders 24 hours before start time"""
    with flask_app.app_context():
        from app.models.booking import Booking
        from app.services.notification_service import notification_service
        
        # Get bookings starting in 24 hours
        reminder_time = datetime.utcnow() + timedelta(hours=24)
        start_window = reminder_time - timedelta(minutes=30)
        end_window = reminder_time + timedelta(minutes=30)
        
        bookings = Booking.query.filter(
            Booking.status == 'confirmed',
            Booking.start_time.between(start_window, end_window)
        ).all()
        
        for booking in bookings:
            notification_service.send_booking_reminder(booking.id)
        
        return f"Sent {len(bookings)} booking reminders"

@celery.task
def process_scheduled_notifications():
    """Process scheduled notifications"""
    with flask_app.app_context():
        return notification_service.process_scheduled_notifications()

@celery.task
def cleanup_expired_rooms():
    """Clean up expired meeting rooms"""
    with flask_app.app_context():
        from app.models.room import Room
        from app import db
        
        # Deactivate expired rooms
        expired_rooms = Room.query.filter(
            Room.expires_at < datetime.utcnow(),
            Room.is_active == True
        ).all()
        
        for room in expired_rooms:
            room.is_active = False
        
        db.session.commit()
        
        return f"Cleaned up {len(expired_rooms)} expired rooms"

@celery.task
def send_email_async(to, subject, template):
    """Send email asynchronously"""
    with flask_app.app_context():
        return send_async_email(to, subject, template)

@celery.task
def update_space_ratings():
    """Update space ratings based on reviews"""
    with flask_app.app_context():
        from app.models.space import Space
        from app import db
        
        spaces = Space.query.all()
        
        for space in spaces:
            space.update_rating()
        
        db.session.commit()
        
        return f"Updated ratings for {len(spaces)} spaces"

@celery.task
def generate_daily_report():
    """Generate daily analytics report"""
    with flask_app.app_context():
        from app.models.user import User
        from app.models.booking import Booking
        from app.models.space import Space
        from sqlalchemy import func
        
        # Get today's statistics
        today = datetime.utcnow().date()
        
        stats = {
            'new_users': User.query.filter(func.date(User.created_at) == today).count(),
            'new_bookings': Booking.query.filter(func.date(Booking.created_at) == today).count(),
            'new_spaces': Space.query.filter(func.date(Space.created_at) == today).count(),
            'total_revenue': float(db.session.query(func.sum(Booking.total_amount)).filter(
                func.date(Booking.created_at) == today,
                Booking.payment_status == 'paid'
            ).scalar() or 0)
        }
        
        # Here you would send this to admin dashboard or email
        return stats

# Celery beat schedule
celery.conf.beat_schedule = {
    'send-booking-reminders': {
        'task': 'celery_app.send_booking_reminders',
        'schedule': 300.0,  # Every 5 minutes
    },
    'process-scheduled-notifications': {
        'task': 'celery_app.process_scheduled_notifications',
        'schedule': 60.0,  # Every minute
    },
    'cleanup-expired-rooms': {
        'task': 'celery_app.cleanup_expired_rooms',
        'schedule': 3600.0,  # Every hour
    },
    'update-space-ratings': {
        'task': 'celery_app.update_space_ratings',
        'schedule': 21600.0,  # Every 6 hours
    },
    'generate-daily-report': {
        'task': 'celery_app.generate_daily_report',
        'schedule': 86400.0,  # Daily
    },
}

celery.conf.timezone = 'UTC'

if __name__ == '__main__':
    celery.start()