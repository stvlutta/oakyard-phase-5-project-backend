from app import db
from datetime import datetime, timedelta
import secrets

class Room(db.Model):
    __tablename__ = 'rooms'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    host_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    room_code = db.Column(db.String(20), unique=True, nullable=False)
    max_participants = db.Column(db.Integer, default=10)
    is_active = db.Column(db.Boolean, default=True)
    is_private = db.Column(db.Boolean, default=False)
    password = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    messages = db.relationship('Message', backref='room', lazy=True, cascade='all, delete-orphan')
    participants = db.relationship('RoomParticipant', backref='room', lazy=True, cascade='all, delete-orphan')
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.room_code:
            self.room_code = self.generate_room_code()
        if not self.expires_at:
            self.expires_at = datetime.utcnow() + timedelta(hours=24)
    
    @staticmethod
    def generate_room_code():
        """Generate a unique room code"""
        while True:
            code = secrets.token_urlsafe(8)[:8].upper()
            if not Room.query.filter_by(room_code=code).first():
                return code
    
    def is_expired(self):
        """Check if room has expired"""
        return datetime.utcnow() > self.expires_at
    
    def get_participant_count(self):
        """Get current number of participants"""
        return RoomParticipant.query.filter_by(room_id=self.id, is_online=True).count()
    
    def can_join(self, user_id):
        """Check if user can join the room"""
        if self.is_expired() or not self.is_active:
            return False
        
        current_participants = self.get_participant_count()
        if current_participants >= self.max_participants:
            return False
        
        # Check if user is already in the room
        existing_participant = RoomParticipant.query.filter_by(
            room_id=self.id, 
            user_id=user_id
        ).first()
        
        return existing_participant is None or not existing_participant.is_online
    
    def add_participant(self, user_id):
        """Add a participant to the room"""
        if not self.can_join(user_id):
            return False
        
        # Check if participant already exists
        participant = RoomParticipant.query.filter_by(
            room_id=self.id, 
            user_id=user_id
        ).first()
        
        if participant:
            # Update existing participant
            participant.is_online = True
            participant.joined_at = datetime.utcnow()
        else:
            # Create new participant
            participant = RoomParticipant(
                room_id=self.id,
                user_id=user_id,
                is_host=(user_id == self.host_id)
            )
            db.session.add(participant)
        
        db.session.commit()
        return True
    
    def remove_participant(self, user_id):
        """Remove a participant from the room"""
        participant = RoomParticipant.query.filter_by(
            room_id=self.id, 
            user_id=user_id
        ).first()
        
        if participant:
            participant.is_online = False
            db.session.commit()
            return True
        
        return False
    
    def to_dict(self, include_host=False, include_participants=False):
        data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'host_id': self.host_id,
            'room_code': self.room_code,
            'max_participants': self.max_participants,
            'current_participants': self.get_participant_count(),
            'is_active': self.is_active,
            'is_private': self.is_private,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'is_expired': self.is_expired()
        }
        
        if include_host and self.host:
            data['host'] = {
                'id': self.host.id,
                'name': self.host.name,
                'avatar_url': self.host.avatar_url
            }
        
        if include_participants:
            data['participants'] = [
                participant.to_dict(include_user=True) 
                for participant in self.participants if participant.is_online
            ]
        
        return data
    
    def __repr__(self):
        return f'<Room {self.name} - {self.room_code}>'

class RoomParticipant(db.Model):
    __tablename__ = 'room_participants'
    
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_host = db.Column(db.Boolean, default=False)
    is_muted = db.Column(db.Boolean, default=False)
    video_enabled = db.Column(db.Boolean, default=True)
    is_online = db.Column(db.Boolean, default=True)
    
    # Constraints
    __table_args__ = (
        db.UniqueConstraint('room_id', 'user_id', name='unique_room_participant'),
    )
    
    def to_dict(self, include_user=False):
        data = {
            'id': self.id,
            'room_id': self.room_id,
            'user_id': self.user_id,
            'joined_at': self.joined_at.isoformat(),
            'is_host': self.is_host,
            'is_muted': self.is_muted,
            'video_enabled': self.video_enabled,
            'is_online': self.is_online
        }
        
        if include_user and self.user:
            data['user'] = {
                'id': self.user.id,
                'name': self.user.name,
                'avatar_url': self.user.avatar_url
            }
        
        return data
    
    def __repr__(self):
        return f'<RoomParticipant {self.user.name} in {self.room.name}>'