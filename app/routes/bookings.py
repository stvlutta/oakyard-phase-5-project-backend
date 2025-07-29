from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from sqlalchemy import and_, or_
from app import db, limiter
from app.models.user import User
from app.models.space import Space
from app.models.booking import Booking
from app.utils.decorators import json_required, validate_json_fields
from app.utils.validators import validate_datetime_format, validate_booking_status
from app.utils.helpers import (
    create_response, create_error_response, paginate_query,
    parse_datetime_from_string, sanitize_input, generate_booking_reference
)
from app.services.payment_service import create_payment_intent, confirm_payment
from app.services.email_service import send_booking_confirmation_email, send_booking_cancellation_email
from sqlalchemy import func
from app.services import payment_service

bookings_bp = Blueprint('bookings', __name__)

@bookings_bp.route('', methods=['GET'])
@jwt_required()
def get_bookings():
    """Get user's bookings"""
    current_user_id = get_jwt_identity()
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status = request.args.get('status')
    
    query = Booking.query.filter_by(user_id=current_user_id)
    
    if status and validate_booking_status(status):
        query = query.filter_by(status=status)
    
    # Date filters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        try:
            start_dt = parse_datetime_from_string(start_date)
            if start_dt:
                query = query.filter(Booking.start_time >= start_dt)
        except ValueError:
            return create_error_response('Invalid start_date format', 400)
    
    if end_date:
        try:
            end_dt = parse_datetime_from_string(end_date)
            if end_dt:
                query = query.filter(Booking.end_time <= end_dt)
        except ValueError:
            return create_error_response('Invalid end_date format', 400)
    
    query = query.order_by(Booking.start_time.desc())
    
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

@bookings_bp.route('/<int:booking_id>', methods=['GET'])
@jwt_required()
def get_booking(booking_id):
    """Get booking details"""
    current_user_id = get_jwt_identity()
    booking = Booking.query.get(booking_id)
    
    if not booking:
        return create_error_response('Booking not found', 404)
    
    # Check permissions
    user = User.query.get(current_user_id)
    if booking.user_id != current_user_id and booking.space.owner_id != current_user_id and user.role != 'admin':
        return create_error_response('Permission denied', 403)
    
    return create_response({
        'booking': booking.to_dict(include_space=True, include_user=True)
    })

@bookings_bp.route('', methods=['POST'])
@jwt_required()
@json_required
@validate_json_fields(['space_id', 'start_time', 'end_time'])
def create_booking():
    """Create a new booking"""
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    space_id = data['space_id']
    start_time_str = data['start_time']
    end_time_str = data['end_time']
    special_requests = sanitize_input(data.get('special_requests', ''), 500)
    
    # Validate space
    space = Space.query.get(space_id)
    if not space or not space.is_active or not space.is_approved:
        return create_error_response('Space not found or not available', 404)
    
    # Parse datetime strings
    start_time = parse_datetime_from_string(start_time_str)
    end_time = parse_datetime_from_string(end_time_str)
    
    if not start_time or not end_time:
        return create_error_response('Invalid datetime format', 400)
    
    # Validate booking times
    if start_time >= end_time:
        return create_error_response('Start time must be before end time', 400)
    
    if start_time < datetime.utcnow():
        return create_error_response('Cannot book in the past', 400)
    
    # Check minimum booking duration (1 hour)
    if (end_time - start_time).total_seconds() < 3600:
        return create_error_response('Minimum booking duration is 1 hour', 400)
    
    # Check maximum booking duration (24 hours)
    if (end_time - start_time).total_seconds() > 86400:
        return create_error_response('Maximum booking duration is 24 hours', 400)
    
    # Check business hours (9 AM to 9 PM)
    if start_time.hour < 9 or end_time.hour > 21:
        return create_error_response('Bookings are only available between 9 AM and 9 PM', 400)
    
    # Check space availability
    if not space.is_available(start_time, end_time):
        return create_error_response('Space is not available during the selected time', 409)
    
    # Calculate total amount
    duration_hours = (end_time - start_time).total_seconds() / 3600
    total_amount = space.hourly_rate * duration_hours
    
    # Create booking
    booking = Booking(
        user_id=current_user_id,
        space_id=space_id,
        start_time=start_time,
        end_time=end_time,
        total_amount=total_amount,
        special_requests=special_requests,
        status='pending'
    )
    
    db.session.add(booking)
    db.session.commit()
    
    # Create payment intent
    try:
        payment_intent = create_payment_intent(
            amount=int(total_amount * 100),  # Convert to cents
            currency='usd',
            metadata={
                'booking_id': booking.id,
                'user_id': current_user_id,
                'space_id': space_id
            }
        )
        
        booking.payment_id = payment_intent['id']
        db.session.commit()
        
        return create_response({
            'booking': booking.to_dict(include_space=True),
            'payment_intent': {
                'id': payment_intent['id'],
                'client_secret': payment_intent['client_secret']
            },
            'message': 'Booking created successfully. Complete payment to confirm.'
        }, 201)
    
    except Exception as e:
        current_app.logger.error(f"Payment intent creation failed: {e}")
        return create_error_response('Failed to create payment intent', 500)

@bookings_bp.route('/<int:booking_id>', methods=['PUT'])
@jwt_required()
@json_required
def update_booking(booking_id):
    """Update booking details"""
    current_user_id = get_jwt_identity()
    booking = Booking.query.get(booking_id)
    
    if not booking:
        return create_error_response('Booking not found', 404)
    
    # Check permissions
    user = User.query.get(current_user_id)
    if booking.user_id != current_user_id and booking.space.owner_id != current_user_id and user.role != 'admin':
        return create_error_response('Permission denied', 403)
    
    data = request.get_json()
    
    # Only allow updates for pending bookings
    if booking.status != 'pending':
        return create_error_response('Only pending bookings can be updated', 400)
    
    # Update special requests
    if 'special_requests' in data:
        booking.special_requests = sanitize_input(data['special_requests'], 500)
    
    # Update booking times (only if user is the booking owner)
    if booking.user_id == current_user_id:
        if 'start_time' in data or 'end_time' in data:
            start_time_str = data.get('start_time')
            end_time_str = data.get('end_time')
            
            if start_time_str:
                start_time = parse_datetime_from_string(start_time_str)
                if not start_time:
                    return create_error_response('Invalid start_time format', 400)
            else:
                start_time = booking.start_time
            
            if end_time_str:
                end_time = parse_datetime_from_string(end_time_str)
                if not end_time:
                    return create_error_response('Invalid end_time format', 400)
            else:
                end_time = booking.end_time
            
            # Validate new times
            if start_time >= end_time:
                return create_error_response('Start time must be before end time', 400)
            
            if start_time < datetime.utcnow():
                return create_error_response('Cannot book in the past', 400)
            
            # Check availability for new times
            if not booking.space.is_available(start_time, end_time):
                return create_error_response('Space is not available during the selected time', 409)
            
            # Update booking
            booking.start_time = start_time
            booking.end_time = end_time
            booking.calculate_total()
    
    db.session.commit()
    
    return create_response({
        'booking': booking.to_dict(include_space=True),
        'message': 'Booking updated successfully'
    })

@bookings_bp.route('/<int:booking_id>/cancel', methods=['POST'])
@jwt_required()
@json_required
def cancel_booking(booking_id):
    """Cancel a booking"""
    current_user_id = get_jwt_identity()
    booking = Booking.query.get(booking_id)
    
    if not booking:
        return create_error_response('Booking not found', 404)
    
    # Check permissions
    user = User.query.get(current_user_id)
    if booking.user_id != current_user_id and user.role != 'admin':
        return create_error_response('Permission denied', 403)
    
    # Check if booking can be cancelled
    if booking.status not in ['pending', 'confirmed']:
        return create_error_response('Booking cannot be cancelled', 400)
    
    if not booking.can_be_cancelled():
        return create_error_response('Booking cannot be cancelled less than 24 hours before start time', 400)
    
    data = request.get_json()
    cancellation_reason = sanitize_input(data.get('reason', ''), 500)
    
    # Cancel booking
    booking.status = 'cancelled'
    booking.cancellation_reason = cancellation_reason
    
    # Handle refund if payment was made
    if booking.payment_status == 'paid':
        try:
            # Process refund (implementation depends on payment provider)
            # For now, just mark as refunded
            booking.payment_status = 'refunded'
        except Exception as e:
            current_app.logger.error(f"Refund processing failed: {e}")
    
    db.session.commit()
    
    # Send cancellation email
    try:
        send_booking_cancellation_email(booking)
    except Exception as e:
        current_app.logger.error(f"Failed to send cancellation email: {e}")
    
    return create_response({
        'booking': booking.to_dict(include_space=True),
        'message': 'Booking cancelled successfully'
    })

@bookings_bp.route('/<int:booking_id>/payment', methods=['POST'])
@jwt_required()
@json_required
@validate_json_fields(['payment_intent_id'])
def process_payment(booking_id):
    """Process payment for a booking"""
    current_user_id = get_jwt_identity()
    booking = Booking.query.get(booking_id)
    
    if not booking:
        return create_error_response('Booking not found', 404)
    
    # Check permissions
    if booking.user_id != current_user_id:
        return create_error_response('Permission denied', 403)
    
    if booking.status != 'pending':
        return create_error_response('Only pending bookings can be paid', 400)
    
    data = request.get_json()
    payment_intent_id = data['payment_intent_id']
    
    try:
        # Confirm payment with Stripe
        payment_intent = confirm_payment(payment_intent_id)
        
        if payment_intent['status'] == 'succeeded':
            booking.status = 'confirmed'
            booking.payment_status = 'paid'
            booking.payment_id = payment_intent_id
            db.session.commit()
            
            # Send confirmation email
            try:
                send_booking_confirmation_email(booking)
            except Exception as e:
                current_app.logger.error(f"Failed to send confirmation email: {e}")
            
            return create_response({
                'booking': booking.to_dict(include_space=True),
                'message': 'Payment processed successfully. Booking confirmed.'
            })
        else:
            return create_error_response('Payment failed', 400)
    
    except Exception as e:
        current_app.logger.error(f"Payment processing failed: {e}")
        return create_error_response('Payment processing failed', 500)

@bookings_bp.route('/<int:booking_id>/complete', methods=['POST'])
@jwt_required()
def complete_booking(booking_id):
    """Mark booking as completed"""
    current_user_id = get_jwt_identity()
    booking = Booking.query.get(booking_id)
    
    if not booking:
        return create_error_response('Booking not found', 404)
    
    # Check permissions (space owner or admin)
    user = User.query.get(current_user_id)
    if booking.space.owner_id != current_user_id and user.role != 'admin':
        return create_error_response('Permission denied', 403)
    
    if booking.status != 'confirmed':
        return create_error_response('Only confirmed bookings can be completed', 400)
    
    if booking.end_time > datetime.utcnow():
        return create_error_response('Booking has not ended yet', 400)
    
    booking.status = 'completed'
    db.session.commit()
    
    return create_response({
        'booking': booking.to_dict(include_space=True),
        'message': 'Booking marked as completed'
    })

@bookings_bp.route('/calendar', methods=['GET'])
@jwt_required()
def get_booking_calendar():
    """Get user's booking calendar"""
    current_user_id = get_jwt_identity()
    
    # Get date range
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date or not end_date:
        return create_error_response('start_date and end_date are required', 400)
    
    try:
        start_dt = parse_datetime_from_string(start_date)
        end_dt = parse_datetime_from_string(end_date)
    except ValueError:
        return create_error_response('Invalid date format', 400)
    
    # Get bookings in date range
    bookings = Booking.query.filter(
        and_(
            Booking.user_id == current_user_id,
            Booking.start_time >= start_dt,
            Booking.end_time <= end_dt,
            Booking.status.in_(['confirmed', 'completed'])
        )
    ).order_by(Booking.start_time.asc()).all()
    
    # Format for calendar display
    calendar_events = []
    for booking in bookings:
        event = {
            'id': booking.id,
            'title': booking.space.title,
            'start': booking.start_time.isoformat(),
            'end': booking.end_time.isoformat(),
            'status': booking.status,
            'space': {
                'id': booking.space.id,
                'title': booking.space.title,
                'address': booking.space.address,
                'category': booking.space.category
            },
            'total_amount': float(booking.total_amount),
            'can_be_cancelled': booking.can_be_cancelled()
        }
        calendar_events.append(event)
    
    return create_response({
        'events': calendar_events,
        'start_date': start_date,
        'end_date': end_date
    })

@bookings_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_booking_stats():
    """Get user's booking statistics"""
    current_user_id = get_jwt_identity()
    
    # Get user's booking stats
    total_bookings = Booking.query.filter_by(user_id=current_user_id).count()
    confirmed_bookings = Booking.query.filter_by(user_id=current_user_id, status='confirmed').count()
    completed_bookings = Booking.query.filter_by(user_id=current_user_id, status='completed').count()
    cancelled_bookings = Booking.query.filter_by(user_id=current_user_id, status='cancelled').count()
    
    # Calculate total spent
    total_spent = db.session.query(func.sum(Booking.total_amount)).filter(
        and_(
            Booking.user_id == current_user_id,
            Booking.status.in_(['confirmed', 'completed'])
        )
    ).scalar() or 0
    
    # Get upcoming bookings
    upcoming_bookings = Booking.query.filter(
        and_(
            Booking.user_id == current_user_id,
            Booking.status == 'confirmed',
            Booking.start_time > datetime.utcnow()
        )
    ).order_by(Booking.start_time.asc()).limit(5).all()
    
    return create_response({
        'stats': {
            'total_bookings': total_bookings,
            'confirmed_bookings': confirmed_bookings,
            'completed_bookings': completed_bookings,
            'cancelled_bookings': cancelled_bookings,
            'total_spent': float(total_spent)
        },
        'upcoming_bookings': [booking.to_dict(include_space=True) for booking in upcoming_bookings]
    })

@bookings_bp.route('/check-availability', methods=['POST'])
@json_required
@validate_json_fields(['space_id', 'start_time', 'end_time'])
def check_availability():
    """Check space availability for given time"""
    data = request.get_json()
    
    space_id = data['space_id']
    start_time_str = data['start_time']
    end_time_str = data['end_time']
    
    # Validate space
    space = Space.query.get(space_id)
    if not space or not space.is_active or not space.is_approved:
        return create_error_response('Space not found or not available', 404)
    
    # Parse datetime strings
    start_time = parse_datetime_from_string(start_time_str)
    end_time = parse_datetime_from_string(end_time_str)
    
    if not start_time or not end_time:
        return create_error_response('Invalid datetime format', 400)
    
    # Check availability
    is_available = space.is_available(start_time, end_time)
    
    # Calculate price
    duration_hours = (end_time - start_time).total_seconds() / 3600
    total_amount = space.hourly_rate * duration_hours
    
    return create_response({
        'available': is_available,
        'duration_hours': duration_hours,
        'total_amount': float(total_amount),
        'hourly_rate': float(space.hourly_rate)
    })

@bookings_bp.route('/create-checkout-session', methods=['POST'])
def create_checkout():
    data = request.get_json()
    amount = data.get('amount')
    currency = data.get('currency', 'usd')
    metadata = data.get('metadata', {})
    if not amount:
        return jsonify({'error': 'Amount is required'}), 400
    url = payment_service.create_checkout_session(amount, currency, metadata)
    if url:
        return jsonify({'checkout_url': url})
    else:
        return jsonify({'error': 'Failed to create checkout session'}), 500