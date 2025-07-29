from app import db
from datetime import datetime
from sqlalchemy import and_, or_

class Space(db.Model):
    __tablename__ = 'spaces'
    
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)  # meeting_room, creative_studio, event_hall, etc.
    hourly_rate = db.Column(db.Numeric(10, 2), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    
    # Location
    address = db.Column(db.Text, nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    
    # Amenities and features
    amenities = db.Column(db.JSON, nullable=True)  # ['wifi', 'projector', 'whiteboard', etc.]
    images = db.Column(db.JSON, nullable=True)  # Array of image URLs
    
    # Status and ratings
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    is_approved = db.Column(db.Boolean, default=False)
    rating_avg = db.Column(db.Float, default=0.0)
    rating_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bookings = db.relationship('Booking', backref='space', lazy=True, cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='space', lazy=True, cascade='all, delete-orphan')
    
    def update_rating(self):
        """Update average rating and count from reviews"""
        if self.reviews:
            self.rating_avg = sum(review.rating for review in self.reviews) / len(self.reviews)
            self.rating_count = len(self.reviews)
        else:
            self.rating_avg = 0.0
            self.rating_count = 0
    
    def is_available(self, start_time, end_time):
        """Check if space is available during the given time period"""
        conflicting_bookings = db.session.query(Booking).filter(
            and_(
                Booking.space_id == self.id,
                Booking.status.in_(['confirmed', 'pending']),
                or_(
                    and_(Booking.start_time <= start_time, Booking.end_time > start_time),
                    and_(Booking.start_time < end_time, Booking.end_time >= end_time),
                    and_(Booking.start_time >= start_time, Booking.end_time <= end_time)
                )
            )
        ).first()
        
        return conflicting_bookings is None
    
    def get_availability_slots(self, date, duration_hours=1):
        """Get available time slots for a given date"""
        from datetime import datetime, time, timedelta
        
        # Get all bookings for the date
        start_of_day = datetime.combine(date, time.min)
        end_of_day = datetime.combine(date, time.max)
        
        bookings = db.session.query(Booking).filter(
            and_(
                Booking.space_id == self.id,
                Booking.status.in_(['confirmed', 'pending']),
                Booking.start_time >= start_of_day,
                Booking.end_time <= end_of_day
            )
        ).order_by(Booking.start_time).all()
        
        # Generate available slots (9 AM to 9 PM)
        available_slots = []
        current_time = datetime.combine(date, time(9, 0))  # 9 AM
        end_time = datetime.combine(date, time(21, 0))  # 9 PM
        
        while current_time + timedelta(hours=duration_hours) <= end_time:
            slot_end = current_time + timedelta(hours=duration_hours)
            
            # Check if this slot conflicts with any booking
            is_available = True
            for booking in bookings:
                if (current_time < booking.end_time and slot_end > booking.start_time):
                    is_available = False
                    break
            
            if is_available:
                available_slots.append({
                    'start_time': current_time.isoformat(),
                    'end_time': slot_end.isoformat()
                })
            
            current_time += timedelta(hours=1)
        
        return available_slots
    
    def to_dict(self, include_owner=False):
        data = {
            'id': self.id,
            'owner_id': self.owner_id,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'hourly_rate': float(self.hourly_rate),
            'capacity': self.capacity,
            'address': self.address,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'amenities': self.amenities or [],
            'images': self.images or [],
            'is_active': self.is_active,
            'is_featured': self.is_featured,
            'is_approved': self.is_approved,
            'rating_avg': self.rating_avg,
            'rating_count': self.rating_count,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        if include_owner and self.owner:
            data['owner'] = {
                'id': self.owner.id,
                'name': self.owner.name,
                'email': self.owner.email,
                'avatar_url': self.owner.avatar_url
            }
        
        return data
    
    def __repr__(self):
        return f'<Space {self.title}>'

# Import here to avoid circular imports
from .booking import Booking