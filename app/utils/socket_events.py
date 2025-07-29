from flask_socketio import emit, join_room, leave_room, disconnect
from flask_jwt_extended import decode_token
from flask import request
from app import socketio, db
from app.models import User, Room, RoomParticipant, Message
from datetime import datetime
import json

# Store active connections
active_connections = {}

@socketio.on('connect')
def handle_connect(auth):
    """Handle client connection"""
    try:
        # Verify JWT token
        token = auth.get('token') if auth else None
        if not token:
            disconnect()
            return
        
        decoded_token = decode_token(token)
        user_id = decoded_token['sub']
        user = User.query.get(user_id)
        
        if not user:
            disconnect()
            return
        
        # Store connection
        active_connections[request.sid] = {
            'user_id': user_id,
            'user_name': user.name,
            'connected_at': datetime.utcnow()
        }
        
        emit('connected', {'message': 'Connected successfully'})
        
    except Exception as e:
        disconnect()

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    if request.sid in active_connections:
        user_info = active_connections[request.sid]
        user_id = user_info['user_id']
        
        # Remove user from all rooms
        participants = RoomParticipant.query.filter_by(user_id=user_id, is_online=True).all()
        for participant in participants:
            participant.is_online = False
            
            # Notify other participants
            emit('participant_left', {
                'user_id': user_id,
                'user_name': user_info['user_name'],
                'room_id': participant.room_id
            }, room=f'room_{participant.room_id}')
        
        db.session.commit()
        del active_connections[request.sid]

@socketio.on('join_room')
def handle_join_room(data):
    """Handle joining a meeting room"""
    try:
        room_id = data.get('room_id')
        password = data.get('password')
        
        if not room_id or request.sid not in active_connections:
            emit('error', {'message': 'Invalid room or not authenticated'})
            return
        
        user_info = active_connections[request.sid]
        user_id = user_info['user_id']
        
        # Get room
        room = Room.query.get(room_id)
        if not room or not room.is_active or room.is_expired():
            emit('error', {'message': 'Room not found or expired'})
            return
        
        # Check password for private rooms
        if room.is_private and room.password != password:
            emit('error', {'message': 'Invalid room password'})
            return
        
        # Check if user can join
        if not room.can_join(user_id):
            emit('error', {'message': 'Cannot join room (full or already joined)'})
            return
        
        # Add participant to room
        if room.add_participant(user_id):
            join_room(f'room_{room_id}')
            
            # Get participant info
            participant = RoomParticipant.query.filter_by(
                room_id=room_id, user_id=user_id
            ).first()
            
            # Notify other participants
            emit('participant_joined', {
                'user_id': user_id,
                'user_name': user_info['user_name'],
                'is_host': participant.is_host,
                'joined_at': participant.joined_at.isoformat()
            }, room=f'room_{room_id}', include_self=False)
            
            # Send room info to the joining user
            emit('room_joined', {
                'room': room.to_dict(include_participants=True),
                'your_participant_id': participant.id
            })
            
            # Send recent messages
            recent_messages = Message.query.filter_by(room_id=room_id)\
                .order_by(Message.created_at.desc()).limit(50).all()
            
            emit('recent_messages', {
                'messages': [msg.to_dict(include_user=True) for msg in reversed(recent_messages)]
            })
        else:
            emit('error', {'message': 'Failed to join room'})
    
    except Exception as e:
        emit('error', {'message': 'An error occurred while joining room'})

@socketio.on('leave_room')
def handle_leave_room(data):
    """Handle leaving a meeting room"""
    try:
        room_id = data.get('room_id')
        
        if not room_id or request.sid not in active_connections:
            emit('error', {'message': 'Invalid room or not authenticated'})
            return
        
        user_info = active_connections[request.sid]
        user_id = user_info['user_id']
        
        # Get room
        room = Room.query.get(room_id)
        if not room:
            emit('error', {'message': 'Room not found'})
            return
        
        # Remove participant from room
        if room.remove_participant(user_id):
            leave_room(f'room_{room_id}')
            
            # Notify other participants
            emit('participant_left', {
                'user_id': user_id,
                'user_name': user_info['user_name']
            }, room=f'room_{room_id}')
            
            emit('room_left', {'message': 'Left room successfully'})
        else:
            emit('error', {'message': 'Failed to leave room'})
    
    except Exception as e:
        emit('error', {'message': 'An error occurred while leaving room'})

@socketio.on('send_message')
def handle_send_message(data):
    """Handle sending a message"""
    try:
        room_id = data.get('room_id')
        message_text = data.get('message')
        message_type = data.get('message_type', 'text')
        
        if not room_id or not message_text or request.sid not in active_connections:
            emit('error', {'message': 'Invalid message data'})
            return
        
        user_info = active_connections[request.sid]
        user_id = user_info['user_id']
        
        # Check if user is in the room
        participant = RoomParticipant.query.filter_by(
            room_id=room_id, user_id=user_id, is_online=True
        ).first()
        
        if not participant:
            emit('error', {'message': 'You are not in this room'})
            return
        
        # Create message
        message = Message(
            room_id=room_id,
            user_id=user_id,
            message=message_text,
            message_type=message_type
        )
        
        db.session.add(message)
        db.session.commit()
        
        # Broadcast message to room
        emit('new_message', message.to_dict(include_user=True), room=f'room_{room_id}')
    
    except Exception as e:
        emit('error', {'message': 'An error occurred while sending message'})

@socketio.on('toggle_mute')
def handle_toggle_mute(data):
    """Handle toggling mute status"""
    try:
        room_id = data.get('room_id')
        is_muted = data.get('is_muted')
        
        if room_id is None or is_muted is None or request.sid not in active_connections:
            emit('error', {'message': 'Invalid data'})
            return
        
        user_info = active_connections[request.sid]
        user_id = user_info['user_id']
        
        # Update participant status
        participant = RoomParticipant.query.filter_by(
            room_id=room_id, user_id=user_id, is_online=True
        ).first()
        
        if participant:
            participant.is_muted = is_muted
            db.session.commit()
            
            # Notify other participants
            emit('participant_status_changed', {
                'user_id': user_id,
                'is_muted': is_muted,
                'video_enabled': participant.video_enabled
            }, room=f'room_{room_id}', include_self=False)
            
            emit('mute_toggled', {'is_muted': is_muted})
        else:
            emit('error', {'message': 'You are not in this room'})
    
    except Exception as e:
        emit('error', {'message': 'An error occurred while toggling mute'})

@socketio.on('toggle_video')
def handle_toggle_video(data):
    """Handle toggling video status"""
    try:
        room_id = data.get('room_id')
        video_enabled = data.get('video_enabled')
        
        if room_id is None or video_enabled is None or request.sid not in active_connections:
            emit('error', {'message': 'Invalid data'})
            return
        
        user_info = active_connections[request.sid]
        user_id = user_info['user_id']
        
        # Update participant status
        participant = RoomParticipant.query.filter_by(
            room_id=room_id, user_id=user_id, is_online=True
        ).first()
        
        if participant:
            participant.video_enabled = video_enabled
            db.session.commit()
            
            # Notify other participants
            emit('participant_status_changed', {
                'user_id': user_id,
                'is_muted': participant.is_muted,
                'video_enabled': video_enabled
            }, room=f'room_{room_id}', include_self=False)
            
            emit('video_toggled', {'video_enabled': video_enabled})
        else:
            emit('error', {'message': 'You are not in this room'})
    
    except Exception as e:
        emit('error', {'message': 'An error occurred while toggling video'})

# WebRTC signaling events
@socketio.on('offer')
def handle_offer(data):
    """Handle WebRTC offer"""
    try:
        room_id = data.get('room_id')
        target_user_id = data.get('target_user_id')
        offer = data.get('offer')
        
        if not all([room_id, target_user_id, offer]):
            emit('error', {'message': 'Invalid offer data'})
            return
        
        user_info = active_connections[request.sid]
        user_id = user_info['user_id']
        
        # Find target user's socket
        target_sid = None
        for sid, conn_info in active_connections.items():
            if conn_info['user_id'] == target_user_id:
                target_sid = sid
                break
        
        if target_sid:
            emit('offer', {
                'from_user_id': user_id,
                'offer': offer,
                'room_id': room_id
            }, room=target_sid)
        else:
            emit('error', {'message': 'Target user not found'})
    
    except Exception as e:
        emit('error', {'message': 'An error occurred while sending offer'})

@socketio.on('answer')
def handle_answer(data):
    """Handle WebRTC answer"""
    try:
        room_id = data.get('room_id')
        target_user_id = data.get('target_user_id')
        answer = data.get('answer')
        
        if not all([room_id, target_user_id, answer]):
            emit('error', {'message': 'Invalid answer data'})
            return
        
        user_info = active_connections[request.sid]
        user_id = user_info['user_id']
        
        # Find target user's socket
        target_sid = None
        for sid, conn_info in active_connections.items():
            if conn_info['user_id'] == target_user_id:
                target_sid = sid
                break
        
        if target_sid:
            emit('answer', {
                'from_user_id': user_id,
                'answer': answer,
                'room_id': room_id
            }, room=target_sid)
        else:
            emit('error', {'message': 'Target user not found'})
    
    except Exception as e:
        emit('error', {'message': 'An error occurred while sending answer'})

@socketio.on('ice_candidate')
def handle_ice_candidate(data):
    """Handle WebRTC ICE candidate"""
    try:
        room_id = data.get('room_id')
        target_user_id = data.get('target_user_id')
        candidate = data.get('candidate')
        
        if not all([room_id, target_user_id, candidate]):
            emit('error', {'message': 'Invalid ICE candidate data'})
            return
        
        user_info = active_connections[request.sid]
        user_id = user_info['user_id']
        
        # Find target user's socket
        target_sid = None
        for sid, conn_info in active_connections.items():
            if conn_info['user_id'] == target_user_id:
                target_sid = sid
                break
        
        if target_sid:
            emit('ice_candidate', {
                'from_user_id': user_id,
                'candidate': candidate,
                'room_id': room_id
            }, room=target_sid)
        else:
            emit('error', {'message': 'Target user not found'})
    
    except Exception as e:
        emit('error', {'message': 'An error occurred while sending ICE candidate'})

@socketio.on('get_room_participants')
def handle_get_room_participants(data):
    """Get current room participants"""
    try:
        room_id = data.get('room_id')
        
        if not room_id:
            emit('error', {'message': 'Room ID required'})
            return
        
        room = Room.query.get(room_id)
        if not room:
            emit('error', {'message': 'Room not found'})
            return
        
        participants = RoomParticipant.query.filter_by(
            room_id=room_id, is_online=True
        ).all()
        
        emit('room_participants', {
            'participants': [p.to_dict(include_user=True) for p in participants]
        })
    
    except Exception as e:
        emit('error', {'message': 'An error occurred while getting participants'})