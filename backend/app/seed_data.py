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