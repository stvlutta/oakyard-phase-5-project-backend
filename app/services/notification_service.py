from flask import current_app
from datetime import datetime, timedelta
from app import db, redis_client
from app.models.user import User
from app.models.booking import Booking
from app.models.space import Space
from app.services.email_service import send_async_email
import json

class NotificationService:
    def __init__(self):
        self.redis_client = redis_client
    
    def send_push_notification(self, user_id, title, body, data=None):
        """Send push notification to user"""
        # This would integrate with Firebase Cloud Messaging or similar
        # For now, we'll store in Redis for real-time updates
        
        notification = {
            'id': f"notif_{datetime.utcnow().timestamp()}",
            'user_id': user_id,
            'title': title,
            'body': body,
            'data': data or {},
            'timestamp': datetime.utcnow().isoformat(),
            'read': False
        }
        
        # Store in Redis
        key = f"notifications:{user_id}"
        self.redis_client.lpush(key, json.dumps(notification))
        
        # Keep only last 100 notifications
        self.redis_client.ltrim(key, 0, 99)
        
        # Set expiration (30 days)
        self.redis_client.expire(key, 30 * 24 * 60 * 60)
        
        return notification
    
    def get_user_notifications(self, user_id, limit=20):
        """Get user's notifications"""
        key = f"notifications:{user_id}"
        notifications = self.redis_client.lrange(key, 0, limit - 1)
        
        return [json.loads(notif) for notif in notifications]
    
    def mark_notification_read(self, user_id, notification_id):
        """Mark notification as read"""
        key = f"notifications:{user_id}"
        notifications = self.redis_client.lrange(key, 0, -1)
        
        for i, notif_data in enumerate(notifications):
            notif = json.loads(notif_data)
            if notif['id'] == notification_id:
                notif['read'] = True
                self.redis_client.lset(key, i, json.dumps(notif))
                return True
        
        return False
    
    def mark_all_notifications_read(self, user_id):
        """Mark all notifications as read"""
        key = f"notifications:{user_id}"
        notifications = self.redis_client.lrange(key, 0, -1)
        
        for i, notif_data in enumerate(notifications):
            notif = json.loads(notif_data)
            notif['read'] = True
            self.redis_client.lset(key, i, json.dumps(notif))
        
        return len(notifications)
    
    def get_unread_count(self, user_id):
        """Get count of unread notifications"""
        key = f"notifications:{user_id}"
        notifications = self.redis_client.lrange(key, 0, -1)
        
        unread_count = 0
        for notif_data in notifications:
            notif = json.loads(notif_data)
            if not notif['read']:
                unread_count += 1
        
        return unread_count
    
    def send_booking_reminder(self, booking_id, hours_before=24):
        """Send booking reminder notification"""
        booking = Booking.query.get(booking_id)
        if not booking or booking.status != 'confirmed':
            return
        
        # Check if reminder should be sent
        reminder_time = booking.start_time - timedelta(hours=hours_before)
        if datetime.utcnow() < reminder_time:
            return
        
        # Send notification
        self.send_push_notification(
            user_id=booking.user_id,
            title="Booking Reminder",
            body=f"Your booking at {booking.space.title} starts in {hours_before} hours",
            data={
                'type': 'booking_reminder',
                'booking_id': booking.id,
                'space_id': booking.space_id
            }
        )
        
        # Send email if user has email notifications enabled
        user = booking.user
        if user.preferences and user.preferences.get('notifications', {}).get('email_bookings', True):
            # Send email reminder
            pass
    
    def notify_new_booking(self, booking_id):
        """Notify space owner of new booking"""
        booking = Booking.query.get(booking_id)
        if not booking:
            return
        
        space_owner = booking.space.owner
        
        # Send notification to space owner
        self.send_push_notification(
            user_id=space_owner.id,
            title="New Booking Received",
            body=f"New booking for {booking.space.title} from {booking.user.name}",
            data={
                'type': 'new_booking',
                'booking_id': booking.id,
                'space_id': booking.space_id,
                'user_id': booking.user_id
            }
        )
    
    def notify_booking_cancelled(self, booking_id):
        """Notify space owner of cancelled booking"""
        booking = Booking.query.get(booking_id)
        if not booking:
            return
        
        space_owner = booking.space.owner
        
        # Send notification to space owner
        self.send_push_notification(
            user_id=space_owner.id,
            title="Booking Cancelled",
            body=f"Booking for {booking.space.title} has been cancelled",
            data={
                'type': 'booking_cancelled',
                'booking_id': booking.id,
                'space_id': booking.space_id,
                'user_id': booking.user_id
            }
        )
    
    def notify_space_approved(self, space_id):
        """Notify space owner that space was approved"""
        space = Space.query.get(space_id)
        if not space:
            return
        
        # Send notification to space owner
        self.send_push_notification(
            user_id=space.owner_id,
            title="Space Approved",
            body=f"Your space '{space.title}' has been approved and is now live",
            data={
                'type': 'space_approved',
                'space_id': space.id
            }
        )
    
    def notify_space_rejected(self, space_id, reason=None):
        """Notify space owner that space was rejected"""
        space = Space.query.get(space_id)
        if not space:
            return
        
        body = f"Your space '{space.title}' was not approved"
        if reason:
            body += f": {reason}"
        
        # Send notification to space owner
        self.send_push_notification(
            user_id=space.owner_id,
            title="Space Not Approved",
            body=body,
            data={
                'type': 'space_rejected',
                'space_id': space.id,
                'reason': reason
            }
        )
    
    def notify_new_review(self, review_id):
        """Notify space owner of new review"""
        from app.models.review import Review
        
        review = Review.query.get(review_id)
        if not review:
            return
        
        space_owner = review.space.owner
        
        # Send notification to space owner
        self.send_push_notification(
            user_id=space_owner.id,
            title="New Review Received",
            body=f"New {review.rating}-star review for {review.space.title}",
            data={
                'type': 'new_review',
                'review_id': review.id,
                'space_id': review.space_id,
                'rating': review.rating
            }
        )
    
    def notify_payment_failed(self, booking_id):
        """Notify user of failed payment"""
        booking = Booking.query.get(booking_id)
        if not booking:
            return
        
        # Send notification to user
        self.send_push_notification(
            user_id=booking.user_id,
            title="Payment Failed",
            body=f"Payment failed for booking at {booking.space.title}",
            data={
                'type': 'payment_failed',
                'booking_id': booking.id,
                'space_id': booking.space_id
            }
        )
    
    def notify_meeting_invite(self, room_id, user_id, invited_by_id):
        """Notify user of meeting room invite"""
        from app.models.room import Room
        
        room = Room.query.get(room_id)
        inviter = User.query.get(invited_by_id)
        
        if not room or not inviter:
            return
        
        # Send notification to invited user
        self.send_push_notification(
            user_id=user_id,
            title="Meeting Invite",
            body=f"{inviter.name} invited you to join '{room.name}'",
            data={
                'type': 'meeting_invite',
                'room_id': room.id,
                'room_code': room.room_code,
                'invited_by': invited_by_id
            }
        )
    
    def send_bulk_notification(self, user_ids, title, body, data=None):
        """Send notification to multiple users"""
        results = []
        
        for user_id in user_ids:
            try:
                notification = self.send_push_notification(user_id, title, body, data)
                results.append({'user_id': user_id, 'success': True, 'notification': notification})
            except Exception as e:
                results.append({'user_id': user_id, 'success': False, 'error': str(e)})
        
        return results
    
    def schedule_notification(self, user_id, title, body, send_at, data=None):
        """Schedule a notification to be sent later"""
        notification = {
            'user_id': user_id,
            'title': title,
            'body': body,
            'data': data or {},
            'send_at': send_at.isoformat(),
            'created_at': datetime.utcnow().isoformat()
        }
        
        # Store in Redis with expiration
        key = f"scheduled_notifications:{send_at.timestamp()}"
        self.redis_client.setex(key, 7 * 24 * 60 * 60, json.dumps(notification))  # 7 days
        
        return notification
    
    def process_scheduled_notifications(self):
        """Process and send scheduled notifications"""
        # This would be called by a background job/cron
        current_timestamp = datetime.utcnow().timestamp()
        
        # Get all scheduled notifications that should be sent
        pattern = "scheduled_notifications:*"
        keys = self.redis_client.keys(pattern)
        
        sent_count = 0
        
        for key in keys:
            try:
                # Extract timestamp from key
                timestamp = float(key.decode().split(':')[1])
                
                if timestamp <= current_timestamp:
                    # Get notification data
                    notification_data = self.redis_client.get(key)
                    if notification_data:
                        notification = json.loads(notification_data)
                        
                        # Send notification
                        self.send_push_notification(
                            user_id=notification['user_id'],
                            title=notification['title'],
                            body=notification['body'],
                            data=notification['data']
                        )
                        
                        # Delete scheduled notification
                        self.redis_client.delete(key)
                        sent_count += 1
            except Exception as e:
                current_app.logger.error(f"Error processing scheduled notification: {e}")
        
        return sent_count
    
    def get_notification_preferences(self, user_id):
        """Get user's notification preferences"""
        user = User.query.get(user_id)
        if not user or not user.preferences:
            return self.get_default_preferences()
        
        return user.preferences.get('notifications', self.get_default_preferences())
    
    def update_notification_preferences(self, user_id, preferences):
        """Update user's notification preferences"""
        user = User.query.get(user_id)
        if not user:
            return False
        
        if not user.preferences:
            user.preferences = {}
        
        user.preferences['notifications'] = preferences
        db.session.commit()
        
        return True
    
    def get_default_preferences(self):
        """Get default notification preferences"""
        return {
            'email_bookings': True,
            'email_reviews': True,
            'email_marketing': False,
            'push_bookings': True,
            'push_reviews': True,
            'push_meetings': True,
            'push_marketing': False,
            'booking_reminders': True,
            'reminder_hours': 24
        }
    
    def should_send_notification(self, user_id, notification_type):
        """Check if notification should be sent based on user preferences"""
        preferences = self.get_notification_preferences(user_id)
        
        notification_mapping = {
            'booking_reminder': 'booking_reminders',
            'new_booking': 'push_bookings',
            'booking_cancelled': 'push_bookings',
            'new_review': 'push_reviews',
            'meeting_invite': 'push_meetings',
            'payment_failed': 'push_bookings',
            'space_approved': 'push_bookings',
            'space_rejected': 'push_bookings'
        }
        
        preference_key = notification_mapping.get(notification_type)
        if not preference_key:
            return True  # Default to sending if not mapped
        
        return preferences.get(preference_key, True)

# Initialize service
notification_service = NotificationService()