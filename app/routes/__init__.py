from .auth import auth_bp
from .users import users_bp
from .spaces import spaces_bp
from .bookings import bookings_bp
from .admin import admin_bp
from .meetings import meetings_bp

__all__ = ['auth_bp', 'users_bp', 'spaces_bp', 'bookings_bp', 'admin_bp', 'meetings_bp']