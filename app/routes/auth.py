from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from app import db, limiter
from app.models.user import User
from app.utils.decorators import json_required, validate_json_fields
from app.utils.validators import validate_email_format, validate_password_strength
from app.utils.helpers import create_response, create_error_response
from app.services.email_service import send_verification_email, send_password_reset_email
from datetime import datetime
import re

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
@limiter.limit("5 per minute")
@json_required
@validate_json_fields(['email', 'password', 'name'])
def register():
    """Register a new user"""
    data = request.get_json()
    
    # Validate input
    email = data['email'].lower().strip()
    password = data['password']
    name = data['name'].strip()
    phone = data.get('phone', '').strip()
    role = data.get('role', 'user')
    
    # Validate email format
    if not validate_email_format(email):
        return create_error_response('Invalid email format', 400)
    
    # Validate password strength
    is_valid, message = validate_password_strength(password)
    if not is_valid:
        return create_error_response(message, 400)
    
    # Validate name
    if len(name) < 2 or len(name) > 100:
        return create_error_response('Name must be between 2 and 100 characters', 400)
    
    # Validate role
    if role not in ['user', 'owner']:
        return create_error_response('Invalid role', 400)
    
    # Check if user already exists
    if User.query.filter_by(email=email).first():
        return create_error_response('User with this email already exists', 409)
    
    # Create new user
    user = User(
        email=email,
        name=name,
        phone=phone,
        role=role
    )
    user.set_password(password)
    
    # Generate email verification token
    verification_token = user.generate_email_verification_token()
    
    db.session.add(user)
    db.session.commit()
    
    # Send verification email
    try:
        send_verification_email(user.email, user.name, verification_token)
    except Exception as e:
        current_app.logger.error(f"Failed to send verification email: {e}")
    
    return create_response({
        'user': user.to_dict(),
        'message': 'User registered successfully. Please check your email to verify your account.'
    }, 201)

@auth_bp.route('/login', methods=['POST'])
@limiter.limit("10 per minute")
@json_required
@validate_json_fields(['email', 'password'])
def login():
    """Login user"""
    data = request.get_json()
    
    email = data['email'].lower().strip()
    password = data['password']
    
    # Find user
    user = User.query.filter_by(email=email).first()
    
    if not user or not user.check_password(password):
        return create_error_response('Invalid email or password', 401)
    
    if not user.is_active:
        return create_error_response('Account has been deactivated', 401)
    
    # Generate tokens
    access_token, refresh_token = user.generate_tokens()
    
    return create_response({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user.to_dict()
    })

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user or not user.is_active:
        return create_error_response('Invalid user', 401)
    
    access_token = create_access_token(identity=current_user_id)
    
    return create_response({
        'access_token': access_token
    })

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user (client-side token invalidation)"""
    return create_response({
        'message': 'Logged out successfully'
    })

@auth_bp.route('/verify-email/<token>', methods=['GET'])
def verify_email(token):
    """Verify email address"""
    user = User.query.filter_by(email_verification_token=token).first()
    
    if not user:
        return create_error_response('Invalid or expired verification token', 400)
    
    user.email_verified = True
    user.email_verification_token = None
    db.session.commit()
    
    return create_response({
        'message': 'Email verified successfully'
    })

@auth_bp.route('/forgot-password', methods=['POST'])
@limiter.limit("3 per minute")
@json_required
@validate_json_fields(['email'])
def forgot_password():
    """Request password reset"""
    data = request.get_json()
    email = data['email'].lower().strip()
    
    # Validate email format
    if not validate_email_format(email):
        return create_error_response('Invalid email format', 400)
    
    user = User.query.filter_by(email=email).first()
    
    if user:
        # Generate password reset token
        reset_token = user.generate_password_reset_token()
        db.session.commit()
        
        # Send password reset email
        try:
            send_password_reset_email(user.email, user.name, reset_token)
        except Exception as e:
            current_app.logger.error(f"Failed to send password reset email: {e}")
    
    # Always return success to prevent email enumeration
    return create_response({
        'message': 'If an account with this email exists, a password reset link has been sent.'
    })

@auth_bp.route('/reset-password', methods=['POST'])
@limiter.limit("5 per minute")
@json_required
@validate_json_fields(['token', 'password'])
def reset_password():
    """Reset password with token"""
    data = request.get_json()
    token = data['token']
    password = data['password']
    
    # Validate password strength
    is_valid, message = validate_password_strength(password)
    if not is_valid:
        return create_error_response(message, 400)
    
    # Find user with token
    user = User.query.filter_by(password_reset_token=token).first()
    
    if not user or not user.verify_password_reset_token(token):
        return create_error_response('Invalid or expired reset token', 400)
    
    # Update password
    user.set_password(password)
    user.password_reset_token = None
    user.password_reset_expires = None
    db.session.commit()
    
    return create_response({
        'message': 'Password reset successfully'
    })

@auth_bp.route('/resend-verification', methods=['POST'])
@limiter.limit("3 per minute")
@json_required
@validate_json_fields(['email'])
def resend_verification():
    """Resend email verification"""
    data = request.get_json()
    email = data['email'].lower().strip()
    
    user = User.query.filter_by(email=email).first()
    
    if not user:
        return create_error_response('User not found', 404)
    
    if user.email_verified:
        return create_error_response('Email already verified', 400)
    
    # Generate new verification token
    verification_token = user.generate_email_verification_token()
    db.session.commit()
    
    # Send verification email
    try:
        send_verification_email(user.email, user.name, verification_token)
    except Exception as e:
        current_app.logger.error(f"Failed to send verification email: {e}")
        return create_error_response('Failed to send verification email', 500)
    
    return create_response({
        'message': 'Verification email sent successfully'
    })

@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
@json_required
@validate_json_fields(['current_password', 'new_password'])
def change_password():
    """Change password for authenticated user"""
    data = request.get_json()
    current_password = data['current_password']
    new_password = data['new_password']
    
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return create_error_response('User not found', 404)
    
    # Verify current password
    if not user.check_password(current_password):
        return create_error_response('Current password is incorrect', 400)
    
    # Validate new password
    is_valid, message = validate_password_strength(new_password)
    if not is_valid:
        return create_error_response(message, 400)
    
    # Update password
    user.set_password(new_password)
    db.session.commit()
    
    return create_response({
        'message': 'Password changed successfully'
    })

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current user profile"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return create_error_response('User not found', 404)
    
    return create_response({
        'user': user.to_dict()
    })