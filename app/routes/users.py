from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from app import db, limiter
from app.models.user import User
from app.models.space import Space
from app.models.booking import Booking
from app.models.review import Review
from app.utils.decorators import json_required, validate_json_fields
from app.utils.validators import validate_email_format, validate_phone_number, validate_image_file
from app.utils.helpers import (
    create_response, create_error_response, save_uploaded_file, 
    delete_file, get_file_url, paginate_query, sanitize_input
)
import os

users_bp = Blueprint('users', __name__)

@users_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get current user profile"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return create_error_response('User not found', 404)
    
    return create_response({
        'user': user.to_dict()
    })

@users_bp.route('/profile', methods=['PUT'])
@jwt_required()
@json_required
def update_profile():
    """Update current user profile"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return create_error_response('User not found', 404)
    
    data = request.get_json()
    
    # Update allowed fields
    if 'name' in data:
        name = sanitize_input(data['name'], 100)
        if len(name) < 2:
            return create_error_response('Name must be at least 2 characters', 400)
        user.name = name
    
    if 'phone' in data:
        phone = sanitize_input(data['phone'], 20)
        if phone and not validate_phone_number(phone):
            return create_error_response('Invalid phone number format', 400)
        user.phone = phone
    
    if 'address' in data:
        user.address = sanitize_input(data['address'], 500)
    
    if 'bio' in data:
        user.bio = sanitize_input(data['bio'], 1000)
    
    if 'preferences' in data:
        if isinstance(data['preferences'], dict):
            user.preferences = data['preferences']
        else:
            return create_error_response('Preferences must be a JSON object', 400)
    
    # Only allow role change for admins
    if 'role' in data and user.role == 'admin':
        if data['role'] in ['user', 'owner', 'admin']:
            user.role = data['role']
    
    db.session.commit()
    
    return create_response({
        'user': user.to_dict(),
        'message': 'Profile updated successfully'
    })

@users_bp.route('/avatar', methods=['POST'])
@jwt_required()
@limiter.limit("5 per minute")
def upload_avatar():
    """Upload user avatar"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return create_error_response('User not found', 404)
    
    if 'file' not in request.files:
        return create_error_response('No file provided', 400)
    
    file = request.files['file']
    
    if file.filename == '':
        return create_error_response('No file selected', 400)
    
    if not validate_image_file(file.filename):
        return create_error_response('Invalid file type. Only images are allowed.', 400)
    
    # Delete old avatar if exists
    if user.avatar_url:
        old_filename = user.avatar_url.split('/')[-1]
        delete_file(old_filename, 'avatars')
    
    # Save new avatar
    filename = save_uploaded_file(file, 'avatars', max_size=(200, 200))
    
    if filename:
        user.avatar_url = get_file_url(filename, 'avatars')
        db.session.commit()
        
        return create_response({
            'avatar_url': user.avatar_url,
            'message': 'Avatar uploaded successfully'
        })
    else:
        return create_error_response('Failed to upload avatar', 500)

@users_bp.route('/avatar', methods=['DELETE'])
@jwt_required()
def delete_avatar():
    """Delete user avatar"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return create_error_response('User not found', 404)
    
    if user.avatar_url:
        filename = user.avatar_url.split('/')[-1]
        delete_file(filename, 'avatars')
        user.avatar_url = None
        db.session.commit()
    
    return create_response({
        'message': 'Avatar deleted successfully'
    })

@users_bp.route('/<int:user_id>/spaces', methods=['GET'])
def get_user_spaces(user_id):
    """Get spaces owned by a user"""
    user = User.query.get(user_id)
    
    if not user:
        return create_error_response('User not found', 404)
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    query = Space.query.filter_by(owner_id=user_id, is_active=True, is_approved=True)
    
    # Apply filters
    category = request.args.get('category')
    if category:
        query = query.filter_by(category=category)
    
    pagination = paginate_query(query, page, per_page)
    
    return create_response({
        'spaces': [space.to_dict() for space in pagination['items']],
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

@users_bp.route('/<int:user_id>/reviews', methods=['GET'])
def get_user_reviews(user_id):
    """Get reviews written by a user"""
    user = User.query.get(user_id)
    
    if not user:
        return create_error_response('User not found', 404)
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    query = Review.query.filter_by(user_id=user_id).order_by(Review.created_at.desc())
    
    pagination = paginate_query(query, page, per_page)
    
    return create_response({
        'reviews': [review.to_dict() for review in pagination['items']],
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

@users_bp.route('/bookings', methods=['GET'])
@jwt_required()
def get_user_bookings():
    """Get current user's bookings"""
    current_user_id = get_jwt_identity()
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status = request.args.get('status')
    
    query = Booking.query.filter_by(user_id=current_user_id).order_by(Booking.created_at.desc())
    
    if status:
        query = query.filter_by(status=status)
    
    pagination = paginate_query(query, page, per_page)
    
    return create_response({
        'bookings': [booking.to_dict(include_space=True) for booking in pagination['items']],
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

@users_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard():
    """Get user dashboard data"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return create_error_response('User not found', 404)
    
    # Get user statistics
    total_bookings = Booking.query.filter_by(user_id=current_user_id).count()
    active_bookings = Booking.query.filter_by(user_id=current_user_id, status='confirmed').count()
    
    # Get recent bookings
    recent_bookings = Booking.query.filter_by(user_id=current_user_id)\
        .order_by(Booking.created_at.desc()).limit(5).all()
    
    dashboard_data = {
        'user': user.to_dict(),
        'stats': {
            'total_bookings': total_bookings,
            'active_bookings': active_bookings,
            'total_reviews': Review.query.filter_by(user_id=current_user_id).count()
        },
        'recent_bookings': [booking.to_dict(include_space=True) for booking in recent_bookings]
    }
    
    # Add owner-specific data
    if user.role in ['owner', 'admin']:
        total_spaces = Space.query.filter_by(owner_id=current_user_id).count()
        active_spaces = Space.query.filter_by(owner_id=current_user_id, is_active=True).count()
        
        dashboard_data['owner_stats'] = {
            'total_spaces': total_spaces,
            'active_spaces': active_spaces,
            'pending_approval': Space.query.filter_by(owner_id=current_user_id, is_approved=False).count()
        }
        
        # Get recent bookings for owner's spaces
        owner_bookings = db.session.query(Booking).join(Space)\
            .filter(Space.owner_id == current_user_id)\
            .order_by(Booking.created_at.desc()).limit(5).all()
        
        dashboard_data['owner_bookings'] = [booking.to_dict(include_space=True, include_user=True) 
                                          for booking in owner_bookings]
    
    return create_response(dashboard_data)

@users_bp.route('/settings', methods=['GET'])
@jwt_required()
def get_user_settings():
    """Get user settings and preferences"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return create_error_response('User not found', 404)
    
    settings = {
        'notifications': user.preferences.get('notifications', {
            'email_bookings': True,
            'email_reviews': True,
            'email_marketing': False,
            'push_notifications': True
        }) if user.preferences else {
            'email_bookings': True,
            'email_reviews': True,
            'email_marketing': False,
            'push_notifications': True
        },
        'privacy': user.preferences.get('privacy', {
            'show_profile': True,
            'show_reviews': True,
            'show_bookings': False
        }) if user.preferences else {
            'show_profile': True,
            'show_reviews': True,
            'show_bookings': False
        }
    }
    
    return create_response({'settings': settings})

@users_bp.route('/settings', methods=['PUT'])
@jwt_required()
@json_required
def update_user_settings():
    """Update user settings and preferences"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return create_error_response('User not found', 404)
    
    data = request.get_json()
    
    # Initialize preferences if not exists
    if not user.preferences:
        user.preferences = {}
    
    # Update notifications settings
    if 'notifications' in data:
        user.preferences['notifications'] = data['notifications']
    
    # Update privacy settings
    if 'privacy' in data:
        user.preferences['privacy'] = data['privacy']
    
    db.session.commit()
    
    return create_response({
        'message': 'Settings updated successfully',
        'settings': {
            'notifications': user.preferences.get('notifications', {}),
            'privacy': user.preferences.get('privacy', {})
        }
    })

@users_bp.route('/deactivate', methods=['POST'])
@jwt_required()
@json_required
@validate_json_fields(['password'])
def deactivate_account():
    """Deactivate user account"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return create_error_response('User not found', 404)
    
    data = request.get_json()
    password = data['password']
    
    # Verify password
    if not user.check_password(password):
        return create_error_response('Invalid password', 400)
    
    # Deactivate account
    user.is_active = False
    db.session.commit()
    
    return create_response({
        'message': 'Account deactivated successfully'
    })