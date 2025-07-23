import os
from datetime import timedelta
from decouple import config

class Config:
    SECRET_KEY = config('SECRET_KEY', default='your-secret-key-here')
    JWT_SECRET_KEY = config('JWT_SECRET_KEY', default='jwt-secret-key-here')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # Database
    SQLALCHEMY_DATABASE_URI = config('DATABASE_URL', default='sqlite:///oakyard.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Email configuration
    MAIL_SERVER = config('MAIL_SERVER', default='smtp.gmail.com')
    MAIL_PORT = config('MAIL_PORT', default=587, cast=int)
    MAIL_USE_TLS = config('MAIL_USE_TLS', default=True, cast=bool)
    MAIL_USERNAME = config('MAIL_USERNAME', default='')
    MAIL_PASSWORD = config('MAIL_PASSWORD', default='')
    MAIL_DEFAULT_SENDER = config('MAIL_DEFAULT_SENDER', default='noreply@oakyard.com')
    
    # Redis
    REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')
    
    # Celery
    CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
    
    # File upload
    UPLOAD_FOLDER = config('UPLOAD_FOLDER', default='uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # AWS S3 (optional)
    AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default='')
    AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default='')
    AWS_S3_BUCKET = config('AWS_S3_BUCKET', default='')
    AWS_S3_REGION = config('AWS_S3_REGION', default='us-east-1')
    
    # Stripe
    STRIPE_PUBLISHABLE_KEY = config('STRIPE_PUBLISHABLE_KEY', default='')
    STRIPE_SECRET_KEY = config('STRIPE_SECRET_KEY', default='')
    STRIPE_WEBHOOK_SECRET = config('STRIPE_WEBHOOK_SECRET', default='')
    
    # Rate limiting
    RATELIMIT_STORAGE_URL = config('RATELIMIT_STORAGE_URL', default='redis://localhost:6379/1')
    
    # CORS
    CORS_ORIGINS = ["http://localhost:8080"]
    
    # Socket.IO
    SOCKETIO_CORS_ALLOWED_ORIGINS = config('SOCKETIO_CORS_ALLOWED_ORIGINS', default='http://localhost:5173,http://localhost:3000').split(',')

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False

config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig
}