from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from sqlalchemy import and_, or_, func
from datetime import datetime, timedelta
from app import db, limiter
from app.models.user import User
from app.models.space import Space
from app.models.booking import Booking
from app.models.review import Review
from app.utils.decorators import json_required, validate_json_fields, owner_required
from app.utils.validators import validate_space_category, validate_coordinates, validate_image_file
from app.utils.helpers import (
    create_response, create_error_response, save_uploaded_file, 
    delete_file, get_file_url, paginate_query, sanitize_input,
    calculate_distance, parse_datetime_from_string
)
import os

spaces_bp = Blueprint('spaces', __name__)

@spaces_bp.route('', methods=['GET'])
def get_spaces():
    """Get list of spaces with search and filtering"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 12, type=int)
    
    # Base query - only active and approved spaces
    query = Space.query.filter_by(is_active=True, is_approved=True)
    
    # Search filters
    search_query = request.args.get('query', '').strip()
    if search_query:
        query = query.filter(
            or_(
                Space.title.ilike(f'%{search_query}%'),
                Space.description.ilike(f'%{search_query}%'),
                Space.address.ilike(f'%{search_query}%')
            )
        )
    
    # Category filter
    category = request.args.get('category')
    if category and validate_space_category(category):
        query = query.filter_by(category=category)
    
    # Price range filter
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    if min_price is not None:
        query = query.filter(Space.hourly_rate >= min_price)
    if max_price is not None:
        query = query.filter(Space.hourly_rate <= max_price)
    
    # Capacity filter
    capacity = request.args.get('capacity', type=int)
    if capacity:
        query = query.filter(Space.capacity >= capacity)
    
    # Amenities filter
    amenities = request.args.getlist('amenities')
    if amenities:
        for amenity in amenities:
            query = query.filter(Space.amenities.contains([amenity]))
    
    # Location-based filter
    latitude = request.args.get('latitude', type=float)
    longitude = request.args.get('longitude', type=float)
    radius = request.args.get('radius', 25, type=float)  # Default 25km radius
    
    if latitude and longitude:
        # For simplicity, using a bounding box instead of haversine distance
        # In production, consider using PostGIS for proper geospatial queries
        lat_offset = radius / 111.0  # Approximate km per degree latitude
        lng_offset = radius / (111.0 * func.cos(func.radians(latitude)))
        
        query = query.filter(
            and_(
                Space.latitude.between(latitude - lat_offset, latitude + lat_offset),
                Space.longitude.between(longitude - lng_offset, longitude + lng_offset)
            )
        )
    
    # Sorting
    sort_by = request.args.get('sort', 'created_at')
    sort_order = request.args.get('order', 'desc')
    
    if sort_by == 'price':
        order_column = Space.hourly_rate
    elif sort_by == 'rating':
        order_column = Space.rating_avg
    elif sort_by == 'capacity':
        order_column = Space.capacity
    else:
        order_column = Space.created_at
    
    if sort_order == 'asc':
        query = query.order_by(order_column.asc())
    else:
        query = query.order_by(order_column.desc())
    
    # Featured spaces first
    featured = request.args.get('featured', type=bool)
    if featured:
        query = query.filter_by(is_featured=True)
    else:
        query = query.order_by(Space.is_featured.desc(), order_column.desc())
    
    pagination = paginate_query(query, page, per_page)
    
    # Calculate distance for each space if location provided
    spaces_data = []
    for space in pagination['items']:
        space_dict = space.to_dict()
        if latitude and longitude and space.latitude and space.longitude:
            distance = calculate_distance(latitude, longitude, space.latitude, space.longitude)
            space_dict['distance'] = round(distance, 2)
        spaces_data.append(space_dict)
    
    return create_response({
        'spaces': spaces_data,
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

@spaces_bp.route('/<int:space_id>', methods=['GET'])
def get_space(space_id):
    """Get space details"""
    space = Space.query.get(space_id)
    
    if not space or not space.is_active:
        return create_error_response('Space not found', 404)
    
    # Check if space is approved (unless user is owner or admin)
    current_user_id = get_jwt_identity() if get_jwt() else None
    if not space.is_approved:
        if not current_user_id or (current_user_id != space.owner_id and 
                                  User.query.get(current_user_id).role != 'admin'):
            return create_error_response('Space not found', 404)
    
    return create_response({
        'space': space.to_dict(include_owner=True)
    })

@spaces_bp.route('', methods=['POST'])
@jwt_required()
@owner_required
@json_required
@validate_json_fields(['title', 'description', 'category', 'hourly_rate', 'capacity', 'address'])
def create_space():
    """Create a new space"""
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    # Validate input
    title = sanitize_input(data['title'], 200)
    description = sanitize_input(data['description'], 2000)
    category = data['category']
    hourly_rate = data['hourly_rate']
    capacity = data['capacity']
    address = sanitize_input(data['address'], 500)
    
    # Validate category
    if not validate_space_category(category):
        return create_error_response('Invalid space category', 400)
    
    # Validate price
    try:
        hourly_rate = float(hourly_rate)
        if hourly_rate < 0:
            return create_error_response('Price must be positive', 400)
    except (ValueError, TypeError):
        return create_error_response('Invalid price format', 400)
    
    # Validate capacity
    try:
        capacity = int(capacity)
        if capacity < 1:
            return create_error_response('Capacity must be at least 1', 400)
    except (ValueError, TypeError):
        return create_error_response('Invalid capacity format', 400)
    
    # Validate coordinates if provided
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    if latitude is not None and longitude is not None:
        if not validate_coordinates(latitude, longitude):
            return create_error_response('Invalid coordinates', 400)
    
    # Create space
    space = Space(
        owner_id=current_user_id,
        title=title,
        description=description,
        category=category,
        hourly_rate=hourly_rate,
        capacity=capacity,
        address=address,
        latitude=latitude,
        longitude=longitude,
        amenities=data.get('amenities', []),
        is_approved=False  # Spaces need admin approval
    )
    
    db.session.add(space)
    db.session.commit()
    
    return create_response({
        'space': space.to_dict(),
        'message': 'Space created successfully. It will be available after admin approval.'
    }, 201)

@spaces_bp.route('/<int:space_id>', methods=['PUT'])
@jwt_required()
@json_required
def update_space(space_id):
    """Update space details"""
    current_user_id = get_jwt_identity()
    space = Space.query.get(space_id)
    
    if not space:
        return create_error_response('Space not found', 404)
    
    # Check permissions
    user = User.query.get(current_user_id)
    if space.owner_id != current_user_id and user.role != 'admin':
        return create_error_response('Permission denied', 403)
    
    data = request.get_json()
    
    # Update allowed fields
    if 'title' in data:
        space.title = sanitize_input(data['title'], 200)
    
    if 'description' in data:
        space.description = sanitize_input(data['description'], 2000)
    
    if 'category' in data:
        if validate_space_category(data['category']):
            space.category = data['category']
        else:
            return create_error_response('Invalid space category', 400)
    
    if 'hourly_rate' in data:
        try:
            hourly_rate = float(data['hourly_rate'])
            if hourly_rate < 0:
                return create_error_response('Price must be positive', 400)
            space.hourly_rate = hourly_rate
        except (ValueError, TypeError):
            return create_error_response('Invalid price format', 400)
    
    if 'capacity' in data:
        try:
            capacity = int(data['capacity'])
            if capacity < 1:
                return create_error_response('Capacity must be at least 1', 400)
            space.capacity = capacity
        except (ValueError, TypeError):
            return create_error_response('Invalid capacity format', 400)
    
    if 'address' in data:
        space.address = sanitize_input(data['address'], 500)
    
    if 'latitude' in data and 'longitude' in data:
        if validate_coordinates(data['latitude'], data['longitude']):
            space.latitude = data['latitude']
            space.longitude = data['longitude']
        else:
            return create_error_response('Invalid coordinates', 400)
    
    if 'amenities' in data:
        if isinstance(data['amenities'], list):
            space.amenities = data['amenities']
        else:
            return create_error_response('Amenities must be a list', 400)
    
    # Only admins can change approval status
    if 'is_approved' in data and user.role == 'admin':
        space.is_approved = bool(data['is_approved'])
    
    # Only admins can set featured status
    if 'is_featured' in data and user.role == 'admin':
        space.is_featured = bool(data['is_featured'])
    
    db.session.commit()
    
    return create_response({
        'space': space.to_dict(),
        'message': 'Space updated successfully'
    })

@spaces_bp.route('/<int:space_id>', methods=['DELETE'])
@jwt_required()
def delete_space(space_id):
    """Delete space (soft delete)"""
    current_user_id = get_jwt_identity()
    space = Space.query.get(space_id)
    
    if not space:
        return create_error_response('Space not found', 404)
    
    # Check permissions
    user = User.query.get(current_user_id)
    if space.owner_id != current_user_id and user.role != 'admin':
        return create_error_response('Permission denied', 403)
    
    # Check for active bookings
    active_bookings = Booking.query.filter_by(
        space_id=space_id,
        status='confirmed'
    ).filter(Booking.end_time > datetime.utcnow()).count()
    
    if active_bookings > 0:
        return create_error_response('Cannot delete space with active bookings', 400)
    
    # Soft delete
    space.is_active = False
    db.session.commit()
    
    return create_response({
        'message': 'Space deleted successfully'
    })

@spaces_bp.route('/<int:space_id>/images', methods=['POST'])
@jwt_required()
@limiter.limit("10 per minute")
def upload_space_images(space_id):
    """Upload space images"""
    current_user_id = get_jwt_identity()
    space = Space.query.get(space_id)
    
    if not space:
        return create_error_response('Space not found', 404)
    
    # Check permissions
    user = User.query.get(current_user_id)
    if space.owner_id != current_user_id and user.role != 'admin':
        return create_error_response('Permission denied', 403)
    
    if 'files' not in request.files:
        return create_error_response('No files provided', 400)
    
    files = request.files.getlist('files')
    
    if not files or all(file.filename == '' for file in files):
        return create_error_response('No files selected', 400)
    
    uploaded_images = []
    
    for file in files:
        if file.filename and validate_image_file(file.filename):
            filename = save_uploaded_file(file, f'spaces/{space_id}', max_size=(1200, 800))
            if filename:
                image_url = get_file_url(filename, f'spaces/{space_id}')
                uploaded_images.append(image_url)
    
    if uploaded_images:
        # Update space images
        current_images = space.images or []
        current_images.extend(uploaded_images)
        space.images = current_images
        db.session.commit()
        
        return create_response({
            'images': uploaded_images,
            'message': f'{len(uploaded_images)} images uploaded successfully'
        })
    else:
        return create_error_response('No valid images uploaded', 400)

@spaces_bp.route('/<int:space_id>/images/<path:image_name>', methods=['DELETE'])
@jwt_required()
def delete_space_image(space_id, image_name):
    """Delete space image"""
    current_user_id = get_jwt_identity()
    space = Space.query.get(space_id)
    
    if not space:
        return create_error_response('Space not found', 404)
    
    # Check permissions
    user = User.query.get(current_user_id)
    if space.owner_id != current_user_id and user.role != 'admin':
        return create_error_response('Permission denied', 403)
    
    # Remove image from space
    if space.images:
        image_url = get_file_url(image_name, f'spaces/{space_id}')
        if image_url in space.images:
            space.images.remove(image_url)
            db.session.commit()
            
            # Delete file from storage
            delete_file(image_name, f'spaces/{space_id}')
            
            return create_response({
                'message': 'Image deleted successfully'
            })
    
    return create_error_response('Image not found', 404)

@spaces_bp.route('/<int:space_id>/availability', methods=['GET'])
def get_space_availability(space_id):
    """Get space availability"""
    space = Space.query.get(space_id)
    
    if not space or not space.is_active:
        return create_error_response('Space not found', 404)
    
    # Get date and duration parameters
    date_str = request.args.get('date')
    duration = request.args.get('duration', 1, type=int)
    
    if not date_str:
        return create_error_response('Date parameter required', 400)
    
    try:
        date = datetime.fromisoformat(date_str).date()
    except ValueError:
        return create_error_response('Invalid date format', 400)
    
    # Get available time slots
    available_slots = space.get_availability_slots(date, duration)
    
    return create_response({
        'date': date.isoformat(),
        'duration_hours': duration,
        'available_slots': available_slots
    })

@spaces_bp.route('/<int:space_id>/reviews', methods=['GET'])
def get_space_reviews(space_id):
    """Get space reviews"""
    space = Space.query.get(space_id)
    
    if not space or not space.is_active:
        return create_error_response('Space not found', 404)
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    query = Review.query.filter_by(space_id=space_id).order_by(Review.created_at.desc())
    
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

@spaces_bp.route('/<int:space_id>/reviews', methods=['POST'])
@jwt_required()
@json_required
@validate_json_fields(['booking_id', 'rating', 'comment'])
def add_space_review(space_id):
    """Add a review for a space"""
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    space = Space.query.get(space_id)
    if not space or not space.is_active:
        return create_error_response('Space not found', 404)
    
    booking_id = data['booking_id']
    rating = data['rating']
    comment = sanitize_input(data['comment'], 1000)
    
    # Validate rating
    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            return create_error_response('Rating must be between 1 and 5', 400)
    except (ValueError, TypeError):
        return create_error_response('Invalid rating format', 400)
    
    # Verify booking
    booking = Booking.query.get(booking_id)
    if not booking or booking.user_id != current_user_id or booking.space_id != space_id:
        return create_error_response('Invalid booking', 400)
    
    if not booking.can_be_reviewed():
        return create_error_response('Booking cannot be reviewed', 400)
    
    # Check if review already exists
    existing_review = Review.query.filter_by(
        user_id=current_user_id,
        booking_id=booking_id
    ).first()
    
    if existing_review:
        return create_error_response('Review already exists for this booking', 400)
    
    # Create review
    review = Review(
        user_id=current_user_id,
        space_id=space_id,
        booking_id=booking_id,
        rating=rating,
        comment=comment
    )
    
    db.session.add(review)
    
    # Update space rating
    space.update_rating()
    
    db.session.commit()
    
    return create_response({
        'review': review.to_dict(include_user=True),
        'message': 'Review added successfully'
    }, 201)

@spaces_bp.route('/categories', methods=['GET'])
def get_space_categories():
    """Get all space categories"""
    categories = [
        {'value': 'meeting_room', 'label': 'Meeting Room'},
        {'value': 'creative_studio', 'label': 'Creative Studio'},
        {'value': 'event_hall', 'label': 'Event Hall'},
        {'value': 'coworking_space', 'label': 'Coworking Space'},
        {'value': 'conference_room', 'label': 'Conference Room'},
        {'value': 'office_space', 'label': 'Office Space'},
        {'value': 'workshop_space', 'label': 'Workshop Space'},
        {'value': 'studio_space', 'label': 'Studio Space'},
        {'value': 'retail_space', 'label': 'Retail Space'},
        {'value': 'exhibition_space', 'label': 'Exhibition Space'},
        {'value': 'training_room', 'label': 'Training Room'},
        {'value': 'other', 'label': 'Other'}
    ]
    
    return create_response({'categories': categories})

@spaces_bp.route('/featured', methods=['GET'])
def get_featured_spaces():
    """Get featured spaces"""
    limit = request.args.get('limit', 6, type=int)
    
    spaces = Space.query.filter_by(
        is_active=True,
        is_approved=True,
        is_featured=True
    ).order_by(Space.rating_avg.desc()).limit(limit).all()
    
    return create_response({
        'spaces': [space.to_dict() for space in spaces]
    })