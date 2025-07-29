from app import db
from datetime import datetime

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20), default='text')  # text, system, file
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self, include_user=False):
        data = {
            'id': self.id,
            'room_id': self.room_id,
            'user_id': self.user_id,
            'message': self.message,
            'message_type': self.message_type,
            'created_at': self.created_at.isoformat()
        }
        
        if include_user and self.user:
            data['user'] = {
                'id': self.user.id,
                'name': self.user.name,
                'avatar_url': self.user.avatar_url
            }
        
        return data
    
    def __repr__(self):
        return f'<Message {self.id} from {self.user.name}>'