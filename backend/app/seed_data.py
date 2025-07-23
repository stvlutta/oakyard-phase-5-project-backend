from app import create_app, db
from app.models.user import User
from app.models.space import Space
from app.models.booking import Booking
from app.models.review import Review
from app.models.room import Room, RoomParticipant
from app.models.message import Message
from datetime import datetime, timedelta
import random

def create_sample_users():
    """Create sample users"""
    users = []
    
    # Admin user
    admin = User(
        email='admin@oakyard.com',
        name='Admin User',
        role='admin',
        email_verified=True,
        is_active=True
    )
    admin.set_password('admin123')
    users.append(admin)
    
    # Regular users
    user_data = [
        {'email': 'john.doe@example.com', 'name': 'John Doe', 'role': 'user'},
        {'email': 'jane.smith@example.com', 'name': 'Jane Smith', 'role': 'user'},
        {'email': 'mike.johnson@example.com', 'name': 'Mike Johnson', 'role': 'user'},
        {'email': 'sarah.wilson@example.com', 'name': 'Sarah Wilson', 'role': 'user'},
        {'email': 'david.brown@example.com', 'name': 'David Brown', 'role': 'user'},
    ]
    
    for user_info in user_data:
        user = User(
            email=user_info['email'],
            name=user_info['name'],
            role=user_info['role'],
            email_verified=True,
            is_active=True,
            phone=f'+1-555-{random.randint(100, 999)}-{random.randint(1000, 9999)}',
            address=f'{random.randint(100, 999)} Main St, City, State {random.randint(10000, 99999)}',
            bio=f'I am {user_info["name"]} and I love using shared spaces for my work.'
        )
        user.set_password('password123')
        users.append(user)
    
    # Space owners
    owner_data = [
        {'email': 'alice.owner@example.com', 'name': 'Alice Owner', 'role': 'owner'},
        {'email': 'bob.owner@example.com', 'name': 'Bob Owner', 'role': 'owner'},
        {'email': 'carol.owner@example.com', 'name': 'Carol Owner', 'role': 'owner'},
        {'email': 'daniel.owner@example.com', 'name': 'Daniel Owner', 'role': 'owner'},
    ]
    
    for owner_info in owner_data:
        owner = User(
            email=owner_info['email'],
            name=owner_info['name'],
            role=owner_info['role'],
            email_verified=True,
            is_active=True,
            phone=f'+1-555-{random.randint(100, 999)}-{random.randint(1000, 9999)}',
            address=f'{random.randint(100, 999)} Business Ave, City, State {random.randint(10000, 99999)}',
            bio=f'I am {owner_info["name"]} and I provide amazing spaces for rent.'
        )
        owner.set_password('password123')
        users.append(owner)
    
    return users

def create_sample_spaces(users):
    """Create sample spaces"""
    spaces = []
    
    # Get owners
    owners = [user for user in users if user.role == 'owner']
    
    space_data = [
        {
            'title': 'Downtown Meeting Room',
            'description': 'Modern meeting room in the heart of downtown with all amenities including projector, whiteboard, and high-speed internet.',
            'category': 'meeting_room',
            'hourly_rate': 50.00,
            'capacity': 8,
            'address': '123 Business District, Downtown, City 12345',
            'amenities': ['wifi', 'projector', 'whiteboard', 'coffee', 'parking'],
            'latitude': 40.7128,
            'longitude': -74.0060,
            'is_featured': True
        },
        {
            'title': 'Creative Studio Space',
            'description': 'Bright and spacious creative studio perfect for workshops, photo shoots, and creative sessions.',
            'category': 'creative_studio',
            'hourly_rate': 75.00,
            'capacity': 12,
            'address': '456 Art District, Creative Quarter, City 12346',
            'amenities': ['wifi', 'natural_light', 'sound_system', 'kitchen', 'parking'],
            'latitude': 40.7589,
            'longitude': -73.9851,
            'is_featured': True
        },
        {
            'title': 'Executive Conference Room',
            'description': 'Premium conference room with video conferencing capabilities and executive amenities.',
            'category': 'conference_room',
            'hourly_rate': 100.00,
            'capacity': 15,
            'address': '789 Corporate Center, Business District, City 12347',
            'amenities': ['wifi', 'video_conferencing', 'projector', 'whiteboard', 'catering', 'parking'],
            'latitude': 40.7505,
            'longitude': -73.9934
        }
    ]
    
    for i, space_info in enumerate(space_data):
        owner = owners[i % len(owners)]
        space = Space(
            owner_id=owner.id,
            title=space_info['title'],
            description=space_info['description'],
            category=space_info['category'],
            hourly_rate=space_info['hourly_rate'],
            capacity=space_info['capacity'],
            address=space_info['address'],
            amenities=space_info['amenities'],
            latitude=space_info['latitude'],
            longitude=space_info['longitude'],
            is_approved=True,
            is_active=True,
            is_featured=space_info.get('is_featured', False),
            rating_avg=round(random.uniform(4.0, 5.0), 1),
            rating_count=random.randint(5, 50)
        )
        spaces.append(space)
    
    return spaces