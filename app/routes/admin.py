from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta
from app import db
from app.models.user import User
from app.models.space import Space
from app.models.booking import Booking
from app.models.review import Review
from app.models.room import Room, RoomParticipant
from app.models.message import Message
from app.utils.decorators import admin_required, json_required, validate_json_fields
from app.utils.validators import validate_user_role, validate_space_category
from app.utils.helpers import (
    create_response, create_error_response, paginate_query, sanitize_input
)

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard', methods=['GET'])
@jwt_required()
@admin_required
def get_dashboard():
    """Get admin dashboard statistics"""
    
    # User statistics
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    new_users_today = User.query.filter(
        User.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    ).count()
    
    # Space statistics
    total_spaces = Space.query.count()
    active_spaces = Space.query.filter_by(is_active=True, is_approved=True).count()
    pending_spaces = Space.query.filter_by(is_approved=False, is_active=True).count()
    
    # Booking statistics
    total_bookings = Booking.query.count()
    confirmed_bookings = Booking.query.filter_by(status='confirmed').count()
    today_bookings = Booking.query.filter(
        Booking.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    ).count()
    
    # Revenue statistics
    total_revenue = db.session.query(func.sum(Booking.total_amount)).filter(
        Booking.payment_status == 'paid'
    ).scalar() or 0
    
    today_revenue = db.session.query(func.sum(Booking.total_amount)).filter(
        and_(
            Booking.payment_status == 'paid',
            Booking.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        )
    ).scalar() or 0
    
    # Review statistics
    total_reviews = Review.query.count()
    avg_rating = db.session.query(func.avg(Review.rating)).scalar() or 0
    
    # Meeting room statistics
    total_rooms = Room.query.count()
    active_rooms = Room.query.filter(
        and_(
            Room.is_active == True,
            Room.expires_at > datetime.utcnow()
        )
    ).count()
    
    return create_response({
        'stats': {
            'users': {
                'total': total_users,
                'active': active_users,
                'new_today': new_users_today
            },
            'spaces': {
                'total': total_spaces,
                'active': active_spaces,
                'pending': pending_spaces
            },
            'bookings': {
                'total': total_bookings,
                'confirmed': confirmed_bookings,
                'today': today_bookings
            },
            'revenue': {
                'total': float(total_revenue),
                'today': float(today_revenue)
            },
            'reviews': {
                'total': total_reviews,
                'avg_rating': float(avg_rating)
            },
            'rooms': {
                'total': total_rooms,
                'active': active_rooms
            }
        }
    })

@admin_bp.route('/users', methods=['GET'])
@jwt_required()
@admin_required
def get_users():
    """Get users with filtering and pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    query = User.query
    
    # Search filter
    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            or_(
                User.name.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%')
            )
        )
    
    # Role filter
    role = request.args.get('role')
    if role and validate_user_role(role):
        query = query.filter_by(role=role)
    
    # Status filter
    status = request.args.get('status')
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    
    # Email verification filter
    email_verified = request.args.get('email_verified')
    if email_verified == 'true':
        query = query.filter_by(email_verified=True)
    elif email_verified == 'false':
        query = query.filter_by(email_verified=False)
    
    # Sorting
    sort_by = request.args.get('sort', 'created_at')
    sort_order = request.args.get('order', 'desc')
    
    if sort_by == 'name':
        order_column = User.name
    elif sort_by == 'email':
        order_column = User.email
    elif sort_by == 'role':
        order_column = User.role
    else:
        order_column = User.created_at
    
    if sort_order == 'asc':
        query = query.order_by(order_column.asc())
    else:
        query = query.order_by(order_column.desc())
    
    pagination = paginate_query(query, page, per_page)
    
    return create_response({
        'users': [user.to_dict() for user in pagination['items']],
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

@admin_bp.route('/users/<int:user_id>', methods=['GET'])
@jwt_required()
@admin_required
def get_user(user_id):
    """Get user details"""
    user = User.query.get(user_id)
    
    if not user:
        return create_error_response('User not found', 404)
    
    # Get user statistics
    user_stats = {
        'total_bookings': Booking.query.filter_by(user_id=user_id).count(),
        'confirmed_bookings': Booking.query.filter_by(user_id=user_id, status='confirmed').count(),
        'total_spent': float(db.session.query(func.sum(Booking.total_amount)).filter(
            and_(
                Booking.user_id == user_id,
                Booking.payment_status == 'paid'
            )
        ).scalar() or 0),
        'total_reviews': Review.query.filter_by(user_id=user_id).count(),
        'owned_spaces': Space.query.filter_by(owner_id=user_id).count(),
        'hosted_rooms': Room.query.filter_by(host_id=user_id).count()
    }
    
    return create_response({
        'user': user.to_dict(),
        'stats': user_stats
    })

@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@jwt_required()
@admin_required
@json_required
def update_user(user_id):
    """Update user details"""
    user = User.query.get(user_id)
    
    if not user:
        return create_error_response('User not found', 404)
    
    data = request.get_json()
    
    # Update allowed fields
    if 'name' in data:
        user.name = sanitize_input(data['name'], 100)
    
    if 'email' in data:
        email = data['email'].lower().strip()
        # Check if email is already taken by another user
        existing_user = User.query.filter_by(email=email).filter(User.id != user_id).first()
        if existing_user:
            return create_error_response('Email already taken', 400)
        user.email = email
    
    if 'role' in data:
        if validate_user_role(data['role']):
            user.role = data['role']
        else:
            return create_error_response('Invalid role', 400)
    
    if 'is_active' in data:
        user.is_active = bool(data['is_active'])
    
    if 'email_verified' in data:
        user.email_verified = bool(data['email_verified'])
    
    if 'phone' in data:
        user.phone = sanitize_input(data['phone'], 20)
    
    if 'address' in data:
        user.address = sanitize_input(data['address'], 500)
    
    if 'bio' in data:
        user.bio = sanitize_input(data['bio'], 1000)
    
    db.session.commit()
    
    return create_response({
        'user': user.to_dict(),
        'message': 'User updated successfully'
    })

@admin_bp.route('/users/<int:user_id>/deactivate', methods=['POST'])
@jwt_required()
@admin_required
def deactivate_user(user_id):
    """Deactivate user account"""
    user = User.query.get(user_id)
    
    if not user:
        return create_error_response('User not found', 404)
    
    if user.role == 'admin':
        return create_error_response('Cannot deactivate admin user', 400)
    
    user.is_active = False
    db.session.commit()
    
    return create_response({
        'message': 'User deactivated successfully'
    })

@admin_bp.route('/users/<int:user_id>/activate', methods=['POST'])
@jwt_required()
@admin_required
def activate_user(user_id):
    """Activate user account"""
    user = User.query.get(user_id)
    
    if not user:
        return create_error_response('User not found', 404)
    
    user.is_active = True
    db.session.commit()
    
    return create_response({
        'message': 'User activated successfully'
    })

@admin_bp.route('/spaces', methods=['GET'])
@jwt_required()
@admin_required
def get_spaces():
    """Get spaces with filtering and pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    query = Space.query
    
    # Search filter
    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            or_(
                Space.title.ilike(f'%{search}%'),
                Space.description.ilike(f'%{search}%'),
                Space.address.ilike(f'%{search}%')
            )
        )
    
    # Category filter
    category = request.args.get('category')
    if category and validate_space_category(category):
        query = query.filter_by(category=category)
    
    # Status filter
    status = request.args.get('status')
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    
    # Approval filter
    approval = request.args.get('approval')
    if approval == 'approved':
        query = query.filter_by(is_approved=True)
    elif approval == 'pending':
        query = query.filter_by(is_approved=False)
    
    # Featured filter
    featured = request.args.get('featured')
    if featured == 'true':
        query = query.filter_by(is_featured=True)
    elif featured == 'false':
        query = query.filter_by(is_featured=False)
    
    # Sorting
    sort_by = request.args.get('sort', 'created_at')
    sort_order = request.args.get('order', 'desc')
    
    if sort_by == 'title':
        order_column = Space.title
    elif sort_by == 'category':
        order_column = Space.category
    elif sort_by == 'hourly_rate':
        order_column = Space.hourly_rate
    elif sort_by == 'rating':
        order_column = Space.rating_avg
    else:
        order_column = Space.created_at
    
    if sort_order == 'asc':
        query = query.order_by(order_column.asc())
    else:
        query = query.order_by(order_column.desc())
    
    pagination = paginate_query(query, page, per_page)
    
    return create_response({
        'spaces': [space.to_dict(include_owner=True) for space in pagination['items']],
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

@admin_bp.route('/spaces/<int:space_id>/approve', methods=['POST'])
@jwt_required()
@admin_required
def approve_space(space_id):
    """Approve a space"""
    space = Space.query.get(space_id)
    
    if not space:
        return create_error_response('Space not found', 404)
    
    space.is_approved = True
    db.session.commit()
    
    return create_response({
        'space': space.to_dict(include_owner=True),
        'message': 'Space approved successfully'
    })

@admin_bp.route('/spaces/<int:space_id>/reject', methods=['POST'])
@jwt_required()
@admin_required
def reject_space(space_id):
    """Reject a space"""
    space = Space.query.get(space_id)
    
    if not space:
        return create_error_response('Space not found', 404)
    
    space.is_approved = False
    space.is_active = False
    db.session.commit()
    
    return create_response({
        'space': space.to_dict(include_owner=True),
        'message': 'Space rejected successfully'
    })

@admin_bp.route('/spaces/<int:space_id>/feature', methods=['POST'])
@jwt_required()
@admin_required
def feature_space(space_id):
    """Feature a space"""
    space = Space.query.get(space_id)
    
    if not space:
        return create_error_response('Space not found', 404)
    
    space.is_featured = True
    db.session.commit()
    
    return create_response({
        'space': space.to_dict(include_owner=True),
        'message': 'Space featured successfully'
    })

@admin_bp.route('/spaces/<int:space_id>/unfeature', methods=['POST'])
@jwt_required()
@admin_required
def unfeature_space(space_id):
    """Unfeature a space"""
    space = Space.query.get(space_id)
    
    if not space:
        return create_error_response('Space not found', 404)
    
    space.is_featured = False
    db.session.commit()
    
    return create_response({
        'space': space.to_dict(include_owner=True),
        'message': 'Space unfeatured successfully'
    })

@admin_bp.route('/bookings', methods=['GET'])
@jwt_required()
@admin_required
def get_bookings():
    """Get bookings with filtering and pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    query = Booking.query.join(Space).join(User)
    
    # Status filter
    status = request.args.get('status')
    if status:
        query = query.filter(Booking.status == status)
    
    # Date range filter
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(Booking.start_time >= start_dt)
        except ValueError:
            return create_error_response('Invalid start_date format', 400)
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            query = query.filter(Booking.end_time <= end_dt)
        except ValueError:
            return create_error_response('Invalid end_date format', 400)
    
    # Search filter
    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            or_(
                User.name.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%'),
                Space.title.ilike(f'%{search}%')
            )
        )
    
    # Sorting
    sort_by = request.args.get('sort', 'created_at')
    sort_order = request.args.get('order', 'desc')
    
    if sort_by == 'start_time':
        order_column = Booking.start_time
    elif sort_by == 'total_amount':
        order_column = Booking.total_amount
    elif sort_by == 'status':
        order_column = Booking.status
    else:
        order_column = Booking.created_at
    
    if sort_order == 'asc':
        query = query.order_by(order_column.asc())
    else:
        query = query.order_by(order_column.desc())
    
    pagination = paginate_query(query, page, per_page)
    
    return create_response({
        'bookings': [booking.to_dict(include_space=True, include_user=True) for booking in pagination['items']],
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

@admin_bp.route('/analytics', methods=['GET'])
@jwt_required()
@admin_required
def get_analytics():
    """Get platform analytics"""
    
    # Time range
    days = request.args.get('days', 30, type=int)
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # User registration analytics
    user_registrations = db.session.query(
        func.date(User.created_at).label('date'),
        func.count(User.id).label('count')
    ).filter(
        User.created_at >= start_date
    ).group_by(func.date(User.created_at)).order_by('date').all()
    
    # Booking analytics
    booking_analytics = db.session.query(
        func.date(Booking.created_at).label('date'),
        func.count(Booking.id).label('count'),
        func.sum(Booking.total_amount).label('revenue')
    ).filter(
        Booking.created_at >= start_date,
        Booking.payment_status == 'paid'
    ).group_by(func.date(Booking.created_at)).order_by('date').all()
    
    # Space analytics by category
    space_categories = db.session.query(
        Space.category,
        func.count(Space.id).label('count')
    ).filter(
        Space.is_active == True,
        Space.is_approved == True
    ).group_by(Space.category).all()
    
    # Popular spaces
    popular_spaces = db.session.query(
        Space.id,
        Space.title,
        func.count(Booking.id).label('booking_count')
    ).join(Booking).filter(
        Booking.created_at >= start_date,
        Booking.status.in_(['confirmed', 'completed'])
    ).group_by(Space.id, Space.title).order_by('booking_count DESC').limit(10).all()
    
    return create_response({
        'analytics': {
            'user_registrations': [
                {'date': reg.date.isoformat(), 'count': reg.count}
                for reg in user_registrations
            ],
            'booking_analytics': [
                {
                    'date': booking.date.isoformat(),
                    'count': booking.count,
                    'revenue': float(booking.revenue or 0)
                }
                for booking in booking_analytics
            ],
            'space_categories': [
                {'category': cat.category, 'count': cat.count}
                for cat in space_categories
            ],
            'popular_spaces': [
                {
                    'id': space.id,
                    'title': space.title,
                    'booking_count': space.booking_count
                }
                for space in popular_spaces
            ]
        }
    })

@admin_bp.route('/reviews', methods=['GET'])
@jwt_required()
@admin_required
def get_reviews():
    """Get reviews with filtering and pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    query = Review.query.join(Space).join(User)
    
    # Rating filter
    rating = request.args.get('rating', type=int)
    if rating and 1 <= rating <= 5:
        query = query.filter(Review.rating == rating)
    
    # Search filter
    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            or_(
                User.name.ilike(f'%{search}%'),
                Space.title.ilike(f'%{search}%'),
                Review.comment.ilike(f'%{search}%')
            )
        )
    
    query = query.order_by(Review.created_at.desc())
    
    pagination = paginate_query(query, page, per_page)
    
    return create_response({
        'reviews': [review.to_dict(include_user=True) for review in pagination['items']],
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

@admin_bp.route('/rooms', methods=['GET'])
@jwt_required()
@admin_required
def get_rooms():
    """Get meeting rooms with filtering and pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    query = Room.query.join(User)
    
    # Status filter
    status = request.args.get('status')
    if status == 'active':
        query = query.filter(
            and_(
                Room.is_active == True,
                Room.expires_at > datetime.utcnow()
            )
        )
    elif status == 'expired':
        query = query.filter(Room.expires_at <= datetime.utcnow())
    elif status == 'inactive':
        query = query.filter(Room.is_active == False)
    
    # Search filter
    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            or_(
                Room.name.ilike(f'%{search}%'),
                Room.room_code.ilike(f'%{search}%'),
                User.name.ilike(f'%{search}%')
            )
        )
    
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

@admin_bp.route('/rooms/<int:room_id>/deactivate', methods=['POST'])
@jwt_required()
@admin_required
def deactivate_room(room_id):
    """Deactivate a meeting room"""
    room = Room.query.get(room_id)
    
    if not room:
        return create_error_response('Room not found', 404)
    
    room.is_active = False
    db.session.commit()
    
    return create_response({
        'message': 'Room deactivated successfully'
    })