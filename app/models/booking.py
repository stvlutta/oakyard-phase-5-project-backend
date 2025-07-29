from app import db
from datetime import datetime

class Booking(db.Model):
    __tablename__ = 'bookings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    space_id = db.Column(db.Integer, db.ForeignKey('spaces.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, cancelled, completed
    payment_status = db.Column(db.String(20), default='unpaid')  # unpaid, paid, refunded
    payment_id = db.Column(db.String(100), nullable=True)  # Stripe payment intent ID
    special_requests = db.Column(db.Text, nullable=True)
    cancellation_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    reviews = db.relationship('Review', backref='booking', lazy=True, cascade='all, delete-orphan')
    
    def calculate_total(self):
        """Calculate total amount based on duration and hourly rate"""
        if self.space:
            duration_hours = (self.end_time - self.start_time).total_seconds() / 3600
            self.total_amount = self.space.hourly_rate * duration_hours
        return self.total_amount
    
    def can_be_cancelled(self):
        """Check if booking can be cancelled (24 hours before start time)"""
        from datetime import timedelta
        return datetime.utcnow() < (self.start_time - timedelta(hours=24))
    
    def can_be_reviewed(self):
        """Check if booking can be reviewed (completed and not already reviewed)"""
        return (self.status == 'completed' and 
                datetime.utcnow() > self.end_time and
                not self.reviews)
    
    def to_dict(self, include_space=False, include_user=False):
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'space_id': self.space_id,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'total_amount': float(self.total_amount),
            'status': self.status,
            'payment_status': self.payment_status,
            'payment_id': self.payment_id,
            'special_requests': self.special_requests,
            'cancellation_reason': self.cancellation_reason,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'can_be_cancelled': self.can_be_cancelled(),
            'can_be_reviewed': self.can_be_reviewed()
        }
        
        if include_space and self.space:
            data['space'] = {
                'id': self.space.id,
                'title': self.space.title,
                'category': self.space.category,
                'address': self.space.address,
                'images': self.space.images or []
            }
        
        if include_user and self.user:
            data['user'] = {
                'id': self.user.id,
                'name': self.user.name,
                'email': self.user.email,
                'avatar_url': self.user.avatar_url
            }
        
        return data
    
    def __repr__(self):
        return f'<Booking {self.id} - {self.user.email} - {self.space.title}>'