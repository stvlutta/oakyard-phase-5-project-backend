import re
from datetime import datetime
from email_validator import validate_email, EmailNotValidError
import phonenumbers
from phonenumbers import NumberParseException

def validate_email_format(email):
    """Validate email format"""
    try:
        validate_email(email)
        return True
    except EmailNotValidError:
        return False

def validate_phone_number(phone, country_code='US'):
    """Validate phone number format"""
    try:
        parsed = phonenumbers.parse(phone, country_code)
        return phonenumbers.is_valid_number(parsed)
    except NumberParseException:
        return False

def validate_password_strength(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    
    return True, "Password is valid"

def validate_datetime_format(date_string):
    """Validate datetime format (ISO 8601)"""
    try:
        datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        return True
    except ValueError:
        return False

def validate_rating(rating):
    """Validate rating value (1-5)"""
    try:
        rating = int(rating)
        return 1 <= rating <= 5
    except (ValueError, TypeError):
        return False

def validate_coordinates(lat, lng):
    """Validate latitude and longitude"""
    try:
        lat = float(lat)
        lng = float(lng)
        return -90 <= lat <= 90 and -180 <= lng <= 180
    except (ValueError, TypeError):
        return False

def validate_file_type(filename, allowed_types):
    """Validate file type by extension"""
    if not filename:
        return False
    
    extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return extension in allowed_types

def validate_image_file(filename):
    """Validate image file type"""
    allowed_types = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    return validate_file_type(filename, allowed_types)

def validate_space_category(category):
    """Validate space category"""
    allowed_categories = {
        'meeting_room', 'creative_studio', 'event_hall', 'coworking_space',
        'conference_room', 'office_space', 'workshop_space', 'studio_space',
        'retail_space', 'exhibition_space', 'training_room', 'other'
    }
    return category in allowed_categories

def validate_user_role(role):
    """Validate user role"""
    allowed_roles = {'user', 'owner', 'admin'}
    return role in allowed_roles

def validate_booking_status(status):
    """Validate booking status"""
    allowed_statuses = {'pending', 'confirmed', 'cancelled', 'completed'}
    return status in allowed_statuses

def validate_payment_status(status):
    """Validate payment status"""
    allowed_statuses = {'unpaid', 'paid', 'refunded'}
    return status in allowed_statuses

def sanitize_input(text, max_length=None):
    """Sanitize text input"""
    if not text:
        return ''
    
    # Remove any HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Strip whitespace
    text = text.strip()
    
    # Truncate if max_length specified
    if max_length and len(text) > max_length:
        text = text[:max_length]
    
    return text

def validate_search_params(params):
    """Validate search parameters"""
    valid_params = {
        'query', 'category', 'min_price', 'max_price', 'capacity',
        'latitude', 'longitude', 'radius', 'amenities', 'page', 'per_page'
    }
    
    invalid_params = set(params.keys()) - valid_params
    if invalid_params:
        return False, f"Invalid parameters: {', '.join(invalid_params)}"
    
    # Validate numeric parameters
    numeric_params = ['min_price', 'max_price', 'capacity', 'latitude', 'longitude', 'radius', 'page', 'per_page']
    for param in numeric_params:
        if param in params:
            try:
                float(params[param])
            except (ValueError, TypeError):
                return False, f"Invalid {param}: must be a number"
    
    return True, "Valid parameters"