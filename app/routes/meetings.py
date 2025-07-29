from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from sqlalchemy import or_, and_
from app import db, limiter
from app.models.user import User
from app.models.room import Room, RoomParticipant
from app.models.message import Message
from app.utils.decorators import json_required, validate_json_fields
from app.utils.helpers import (
    create_response, create_error_response, paginate_query,
    sanitize_input, generate_secure_token
)

meetings_bp = Blueprint('meetings', __name__)

@meetings_bp.route('', methods=['GET'])
@jwt_required()
def get_rooms():
    """Get user's meeting rooms"""
    current_user_id = get_jwt_identity()
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # Get rooms where user is host or participant
    query = db.session.query(Room).outerjoin(RoomParticipant).filter(
        or_(
            Room.host_id == current_user_id,
            and_(
                RoomParticipant.user_id == current_user_id,
                RoomParticipant.is_online == True
            )
        )
    ).filter(Room.is_active == True).distinct()
    
    # Filter by status
    status = request.args.get('status')
    if status == 'active':
        query = query.filter(Room.expires_at > datetime.utcnow())
    elif status == 'expired':
        query = query.filter(Room.expires_at <= datetime.utcnow())
    
    query = query.order_by(Room.created_at.desc())
    
    pagination = paginate_query(query, page, per_page)
    
    return create_response({
        'rooms': [room.to_dict(include_host=True) for room in pagination['items']],
        'pagination': {
            'page': pagination['page'],
            'per_page': pagination['per_page'],
            'total': pagination['total'],
            'pages': pagination['pages'],
            'has_prev': pagination['has_prev'],
            'has_next': pagination['has_next'],
            'prev_page': pagination['prev_page'],
            'next_page': pagination['next_page']
        }
    })

@meetings_bp.route('/<int:room_id>', methods=['GET'])
@jwt_required()
def get_room(room_id):
    """Get room details"""
    current_user_id = get_jwt_identity()
    room = Room.query.get(room_id)
    
    if not room:
        return create_error_response('Room not found', 404)
    
    # Check if user has access to this room
    if room.host_id != current_user_id:
        participant = RoomParticipant.query.filter_by(
            room_id=room_id,
            user_id=current_user_id
        ).first()
        
        if not participant and room.is_private:
            return create_error_response('Access denied', 403)
    
    return create_response({
        'room': room.to_dict(include_host=True, include_participants=True)
    })

@meetings_bp.route('', methods=['POST'])
@jwt_required()
@limiter.limit("10 per minute")
@json_required
@validate_json_fields(['name'])
def create_room():
    """Create a new meeting room"""
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    name = sanitize_input(data['name'], 200)
    description = sanitize_input(data.get('description', ''), 1000)
    max_participants = data.get('max_participants', 10)
    is_private = data.get('is_private', False)
    password = data.get('password', '')
    duration_hours = data.get('duration_hours', 24)
    
    # Validate input
    if len(name) < 3:
        return create_error_response('Room name must be at least 3 characters', 400)
    
    try:
        max_participants = int(max_participants)
        if max_participants < 2 or max_participants > 100:
            return create_error_response('Max participants must be between 2 and 100', 400)
    except (ValueError, TypeError):
        return create_error_response('Invalid max_participants format', 400)
    
    try:
        duration_hours = int(duration_hours)
        if duration_hours < 1 or duration_hours > 168:  # Max 7 days
            return create_error_response('Duration must be between 1 and 168 hours', 400)
    except (ValueError, TypeError):
        return create_error_response('Invalid duration_hours format', 400)
    
    # Validate password for private rooms
    if is_private:
        if not password or len(password) < 4:
            return create_error_response('Private rooms require a password of at least 4 characters', 400)
        password = sanitize_input(password, 50)
    else:
        password = None
    
    # Create room
    room = Room(
        name=name,
        description=description,
        host_id=current_user_id,
        max_participants=max_participants,
        is_private=is_private,
        password=password,
        expires_at=datetime.utcnow() + timedelta(hours=duration_hours)
    )
    
    db.session.add(room)
    db.session.commit()
    
    # Add host as participant
    room.add_participant(current_user_id)
    
    return create_response({
        'room': room.to_dict(include_host=True),
        'message': 'Room created successfully'
    }, 201)

@meetings_bp.route('/<int:room_id>', methods=['PUT'])
@jwt_required()
@json_required
def update_room(room_id):
    """Update room details"""
    current_user_id = get_jwt_identity()
    room = Room.query.get(room_id)
    
    if not room:
        return create_error_response('Room not found', 404)
    
    # Check permissions - only host can update
    if room.host_id != current_user_id:
        return create_error_response('Permission denied', 403)
    
    data = request.get_json()
    
    # Update allowed fields
    if 'name' in data:
        name = sanitize_input(data['name'], 200)
        if len(name) < 3:
            return create_error_response('Room name must be at least 3 characters', 400)
        room.name = name
    
    if 'description' in data:
        room.description = sanitize_input(data['description'], 1000)
    
    if 'max_participants' in data:
        try:
            max_participants = int(data['max_participants'])
            if max_participants < 2 or max_participants > 100:
                return create_error_response('Max participants must be between 2 and 100', 400)
            room.max_participants = max_participants
        except (ValueError, TypeError):
            return create_error_response('Invalid max_participants format', 400)
    
    if 'is_private' in data:
        room.is_private = bool(data['is_private'])
    
    if 'password' in data:
        if room.is_private:
            password = sanitize_input(data['password'], 50)
            if len(password) < 4:
                return create_error_response('Password must be at least 4 characters', 400)
            room.password = password
        else:
            room.password = None
    
    if 'expires_at' in data:
        try:
            expires_at = datetime.fromisoformat(data['expires_at'])
            if expires_at <= datetime.utcnow():
                return create_error_response('Expiration time must be in the future', 400)
            room.expires_at = expires_at
        except ValueError:
            return create_error_response('Invalid expires_at format', 400)
    
    db.session.commit()
    
    return create_response({
        'room': room.to_dict(include_host=True),
        'message': 'Room updated successfully'
    })

@meetings_bp.route('/<int:room_id>', methods=['DELETE'])
@jwt_required()
def delete_room(room_id):
    """Delete a meeting room"""
    current_user_id = get_jwt_identity()
    room = Room.query.get(room_id)
    
    if not room:
        return create_error_response('Room not found', 404)
    
    # Check permissions - only host can delete
    if room.host_id != current_user_id:
        return create_error_response('Permission denied', 403)
    
    # Soft delete
    room.is_active = False
    db.session.commit()
    
    return create_response({
        'message': 'Room deleted successfully'
    })

@meetings_bp.route('/<int:room_id>/join', methods=['POST'])
@jwt_required()
@json_required
def join_room(room_id):
    """Join a meeting room"""
    current_user_id = get_jwt_identity()
    room = Room.query.get(room_id)
    
    if not room or not room.is_active:
        return create_error_response('Room not found or inactive', 404)
    
    if room.is_expired():
        return create_error_response('Room has expired', 400)
    
    data = request.get_json()
    password = data.get('password', '')
    
    # Check password for private rooms
    if room.is_private and room.password != password:
        return create_error_response('Invalid room password', 401)
    
    # Check if user can join
    if not room.can_join(current_user_id):
        return create_error_response('Cannot join room (full or already joined)', 400)
    
    # Add participant
    if room.add_participant(current_user_id):
        participant = RoomParticipant.query.filter_by(
            room_id=room_id,
            user_id=current_user_id
        ).first()
        
        return create_response({
            'room': room.to_dict(include_host=True, include_participants=True),
            'participant': participant.to_dict(include_user=True),
            'message': 'Joined room successfully'
        })
    else:
        return create_error_response('Failed to join room', 500)

@meetings_bp.route('/<int:room_id>/leave', methods=['POST'])
@jwt_required()
def leave_room(room_id):
    """Leave a meeting room"""
    current_user_id = get_jwt_identity()
    room = Room.query.get(room_id)
    
    if not room:
        return create_error_response('Room not found', 404)
    
    # Remove participant
    if room.remove_participant(current_user_id):
        return create_response({
            'message': 'Left room successfully'
        })
    else:
        return create_error_response('You are not in this room', 400)

@meetings_bp.route('/<int:room_id>/participants', methods=['GET'])
@jwt_required()
def get_room_participants(room_id):
    """Get room participants"""
    current_user_id = get_jwt_identity()
    room = Room.query.get(room_id)
    
    if not room:
        return create_error_response('Room not found', 404)
    
    # Check if user has access to this room
    if room.host_id != current_user_id:
        participant = RoomParticipant.query.filter_by(
            room_id=room_id,
            user_id=current_user_id,
            is_online=True
        ).first()
        
        if not participant:
            return create_error_response('Access denied', 403)
    
    participants = RoomParticipant.query.filter_by(
        room_id=room_id,
        is_online=True
    ).order_by(RoomParticipant.joined_at.asc()).all()
    
    return create_response({
        'participants': [p.to_dict(include_user=True) for p in participants]
    })

@meetings_bp.route('/<int:room_id>/messages', methods=['GET'])
@jwt_required()
def get_room_messages(room_id):
    """Get room messages"""
    current_user_id = get_jwt_identity()
    room = Room.query.get(room_id)
    
    if not room:
        return create_error_response('Room not found', 404)
    
    # Check if user has access to this room
    if room.host_id != current_user_id:
        participant = RoomParticipant.query.filter_by(
            room_id=room_id,
            user_id=current_user_id,
            is_online=True
        ).first()
        
        if not participant:
            return create_error_response('Access denied', 403)
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    query = Message.query.filter_by(room_id=room_id).order_by(Message.created_at.desc())
    
    pagination = paginate_query(query, page, per_page)
    
    # Reverse to show oldest first
    messages = list(reversed(pagination['items']))
    
    return create_response({
        'messages': [message.to_dict(include_user=True) for message in messages],
        'pagination': {
            'page': pagination['page'],
            'per_page': pagination['per_page'],
            'total': pagination['total'],
            'pages': pagination['pages'],
            'has_prev': pagination['has_prev'],
            'has_next': pagination['has_next'],
            'prev_page': pagination['prev_page'],
            'next_page': pagination['next_page']
        }
    })

@meetings_bp.route('/<int:room_id>/messages', methods=['POST'])
@jwt_required()
@json_required
@validate_json_fields(['message'])
def send_message(room_id):
    """Send a message to the room"""
    current_user_id = get_jwt_identity()
    room = Room.query.get(room_id)
    
    if not room:
        return create_error_response('Room not found', 404)
    
    # Check if user is in the room
    participant = RoomParticipant.query.filter_by(
        room_id=room_id,
        user_id=current_user_id,
        is_online=True
    ).first()
    
    if not participant:
        return create_error_response('You are not in this room', 403)
    
    data = request.get_json()
    message_text = sanitize_input(data['message'], 2000)
    message_type = data.get('message_type', 'text')
    
    if not message_text:
        return create_error_response('Message cannot be empty', 400)
    
    # Create message
    message = Message(
        room_id=room_id,
        user_id=current_user_id,
        message=message_text,
        message_type=message_type
    )
    
    db.session.add(message)
    db.session.commit()
    
    return create_response({
        'message': message.to_dict(include_user=True)
    }, 201)

@meetings_bp.route('/join-by-code', methods=['POST'])
@jwt_required()
@json_required
@validate_json_fields(['room_code'])
def join_room_by_code():
    """Join a room by room code"""
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    room_code = data['room_code'].upper().strip()
    password = data.get('password', '')
    
    # Find room by code
    room = Room.query.filter_by(
        room_code=room_code,
        is_active=True
    ).first()
    
    if not room:
        return create_error_response('Room not found', 404)
    
    if room.is_expired():
        return create_error_response('Room has expired', 400)
    
    # Check password for private rooms
    if room.is_private and room.password != password:
        return create_error_response('Invalid room password', 401)
    
    # Check if user can join
    if not room.can_join(current_user_id):
        return create_error_response('Cannot join room (full or already joined)', 400)
    
    # Add participant
    if room.add_participant(current_user_id):
        participant = RoomParticipant.query.filter_by(
            room_id=room.id,
            user_id=current_user_id
        ).first()
        
        return create_response({
            'room': room.to_dict(include_host=True, include_participants=True),
            'participant': participant.to_dict(include_user=True),
            'message': 'Joined room successfully'
        })
    else:
        return create_error_response('Failed to join room', 500)

@meetings_bp.route('/<int:room_id>/extend', methods=['POST'])
@jwt_required()
@json_required
@validate_json_fields(['hours'])
def extend_room(room_id):
    """Extend room expiration time"""
    current_user_id = get_jwt_identity()
    room = Room.query.get(room_id)
    
    if not room:
        return create_error_response('Room not found', 404)
    
    # Check permissions - only host can extend
    if room.host_id != current_user_id:
        return create_error_response('Permission denied', 403)
    
    data = request.get_json()
    
    try:
        hours = int(data['hours'])
        if hours < 1 or hours > 168:  # Max 7 days
            return create_error_response('Extension must be between 1 and 168 hours', 400)
    except (ValueError, TypeError):
        return create_error_response('Invalid hours format', 400)
    
    # Extend expiration
    room.expires_at = room.expires_at + timedelta(hours=hours)
    db.session.commit()
    
    return create_response({
        'room': room.to_dict(include_host=True),
        'message': f'Room extended by {hours} hours'
    })

@meetings_bp.route('/active', methods=['GET'])
@jwt_required()
def get_active_rooms():
    """Get active rooms for the current user"""
    current_user_id = get_jwt_identity()
    
    # Get rooms where user is currently a participant
    participants = RoomParticipant.query.filter_by(
        user_id=current_user_id,
        is_online=True
    ).all()
    
    active_rooms = []
    for participant in participants:
        room = participant.room
        if room.is_active and not room.is_expired():
            active_rooms.append({
                'room': room.to_dict(include_host=True),
                'participant': participant.to_dict()
            })
    
    return create_response({
        'active_rooms': active_rooms
    })