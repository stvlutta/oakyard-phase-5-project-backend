from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from flask_cors import CORS
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from redis import Redis
from celery import Celery
import os

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
socketio = SocketIO()
cors = CORS()
mail = Mail()
limiter = Limiter(key_func=get_remote_address)
redis_client = Redis()

def create_celery_app(app):
    celery = Celery(app.import_name)
    celery.conf.update(
        broker_url=app.config['CELERY_BROKER_URL'],
        result_backend=app.config['CELERY_RESULT_BACKEND']
    )
    
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery

def create_app(config_name='development'):
    app = Flask(__name__)
    
    # Load configuration
    from .config import config_by_name
    app.config.from_object(config_by_name[config_name])
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, origins=app.config['CORS_ORIGINS'])
    mail.init_app(app)
    limiter.init_app(app)
    socketio.init_app(app, cors_allowed_origins=app.config['SOCKETIO_CORS_ALLOWED_ORIGINS'])
    
    # Initialize Redis
    redis_client.from_url(app.config['REDIS_URL'])
    
    # Create upload folder
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Register blueprints
    from .routes.auth import auth_bp
    from .routes.users import users_bp
    from .routes.spaces import spaces_bp
    from .routes.bookings import bookings_bp
    from .routes.admin import admin_bp
    from .routes.meetings import meetings_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(spaces_bp, url_prefix='/api/spaces')
    app.register_blueprint(bookings_bp, url_prefix='/api/bookings')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(meetings_bp, url_prefix='/api/rooms')
    
    # Import models to ensure they're registered
    from .models import user, space, booking, review, room, message
    
    # Import socket events
    from .utils import socket_events
    
    # JWT error handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return {'message': 'Token has expired'}, 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return {'message': 'Invalid token'}, 401
    
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return {'message': 'Authentication required'}, 401
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return {'message': 'Resource not found'}, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return {'message': 'Internal server error'}, 500
    
    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        return {'message': 'Rate limit exceeded'}, 429
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'message': 'Oakyard API is running'}
    
    return app