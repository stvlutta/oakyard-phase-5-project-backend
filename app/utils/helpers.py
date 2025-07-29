import os
import secrets
from datetime import datetime, timedelta
from PIL import Image
from werkzeug.utils import secure_filename
from flask import current_app
import math

def generate_secure_token(length=32):
    """Generate a secure random token"""
    return secrets.token_urlsafe(length)

def allowed_file(filename, allowed_extensions):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def save_uploaded_file(file, folder, max_size=(800, 600)):
    """Save uploaded file with resizing for images"""
    if not file or not file.filename:
        return None
    
    # Secure the filename
    filename = secure_filename(file.filename)
    
    # Generate unique filename
    name, ext = os.path.splitext(filename)
    unique_filename = f"{name}_{generate_secure_token(8)}{ext}"
    
    # Create folder if it doesn't exist
    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], folder)
    os.makedirs(upload_folder, exist_ok=True)
    
    file_path = os.path.join(upload_folder, unique_filename)
    
    # Save and resize image if it's an image file
    if ext.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
        try:
            image = Image.open(file.stream)
            
            # Resize image if it's too large
            if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Save with optimization
            image.save(file_path, optimize=True, quality=85)
        except Exception as e:
            current_app.logger.error(f"Error processing image: {e}")
            return None
    else:
        file.save(file_path)
    
    return unique_filename

def delete_file(filename, folder):
    """Delete a file from the uploads folder"""
    try:
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], folder, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception as e:
        current_app.logger.error(f"Error deleting file: {e}")
    return False

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates using Haversine formula"""
    R = 6371  # Earth's radius in kilometers
    
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

def paginate_query(query, page, per_page, max_per_page=100):
    """Paginate a SQLAlchemy query"""
    page = max(1, page)
    per_page = min(max_per_page, max(1, per_page))
    
    pagination = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    return {
        'items': pagination.items,
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages,
        'has_prev': pagination.has_prev,
        'has_next': pagination.has_next,
        'prev_page': pagination.prev_num if pagination.has_prev else None,
        'next_page': pagination.next_num if pagination.has_next else None
    }

def format_currency(amount, currency='USD'):
    """Format currency amount"""
    if currency == 'USD':
        return f"${amount:.2f}"
    else:
        return f"{amount:.2f} {currency}"

def generate_booking_reference():
    """Generate a unique booking reference"""
    timestamp = datetime.now().strftime('%Y%m%d')
    random_part = secrets.token_hex(4).upper()
    return f"OY{timestamp}{random_part}"

def calculate_booking_duration(start_time, end_time):
    """Calculate booking duration in hours"""
    duration = end_time - start_time
    return duration.total_seconds() / 3600

def is_business_hours(dt, start_hour=9, end_hour=21):
    """Check if datetime is within business hours"""
    return start_hour <= dt.hour < end_hour

def get_next_business_day(date):
    """Get the next business day (Monday-Friday)"""
    while date.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        date += timedelta(days=1)
    return date

def format_datetime_for_display(dt, format_str='%Y-%m-%d %H:%M'):
    """Format datetime for display"""
    return dt.strftime(format_str)

def parse_datetime_from_string(date_string):
    """Parse datetime from ISO string"""
    try:
        # Handle timezone info
        if date_string.endswith('Z'):
            date_string = date_string[:-1] + '+00:00'
        return datetime.fromisoformat(date_string)
    except ValueError:
        return None

def create_response(data=None, message=None, status_code=200):
    """Create standardized API response"""
    response = {}
    
    if data is not None:
        response['data'] = data
    
    if message:
        response['message'] = message
    
    response['status'] = 'success' if status_code < 400 else 'error'
    response['timestamp'] = datetime.utcnow().isoformat()
    
    return response, status_code

def create_error_response(message, status_code=400, errors=None):
    """Create standardized error response"""
    response = {
        'message': message,
        'status': 'error',
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if errors:
        response['errors'] = errors
    
    return response, status_code

def get_file_url(filename, folder):
    """Get URL for uploaded file"""
    if not filename:
        return None
    
    # In production, this would be an S3 URL or CDN URL
    base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')
    return f"{base_url}/uploads/{folder}/{filename}"

def extract_mentions(text):
    """Extract @mentions from text"""
    import re
    mentions = re.findall(r'@(\w+)', text)
    return mentions

def truncate_text(text, max_length, suffix='...'):
    """Truncate text to max length with suffix"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def sanitize_input(text, max_length=None):
    """Sanitize text input"""
    if not text:
        return ''
    
    # Remove any HTML tags
    import re
    text = re.sub(r'<[^>]+>', '', text)
    
    # Strip whitespace
    text = text.strip()
    
    # Truncate if max_length specified
    if max_length and len(text) > max_length:
        text = text[:max_length]
    
    return text