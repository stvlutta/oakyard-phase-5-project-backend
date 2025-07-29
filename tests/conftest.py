import pytest
from app import create_app, db
from app.models.user import User
from app.models.space import Space
from app.models.booking import Booking

@pytest.fixture
def app():
    """Create application for testing"""
    app = create_app('testing')
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()

@pytest.fixture
def runner(app):
    """Create test runner"""
    return app.test_cli_runner()

@pytest.fixture
def auth_user(app):
    """Create authenticated user"""
    user = User(
        email='test@example.com',
        name='Test User',
        role='user',
        email_verified=True,
        is_active=True
    )
    user.set_password('testpass123')
    
    db.session.add(user)
    db.session.commit()
    
    return user

@pytest.fixture
def auth_headers(client, auth_user):
    """Get authentication headers"""
    response = client.post('/api/auth/login', json={
        'email': 'test@example.com',
        'password': 'testpass123'
    })
    
    data = response.get_json()
    token = data['data']['access_token']
    
    return {'Authorization': f'Bearer {token}'}

@pytest.fixture
def sample_space(app, auth_user):
    """Create sample space"""
    space = Space(
        owner_id=auth_user.id,
        title='Test Space',
        description='A test space',
        category='meeting_room',
        hourly_rate=50.0,
        capacity=10,
        address='123 Test St',
        is_approved=True,
        is_active=True
    )
    
    db.session.add(space)
    db.session.commit()
    
    return space