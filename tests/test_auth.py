import pytest
from app.models.user import User
from app import db

def test_register_user(client):
    """Test user registration"""
    response = client.post('/api/auth/register', json={
        'email': 'newuser@example.com',
        'name': 'New User',
        'password': 'Password123!'
    })
    
    assert response.status_code == 201
    data = response.get_json()
    assert data['status'] == 'success'
    assert 'user' in data['data']
    
    # Check user was created
    user = User.query.filter_by(email='newuser@example.com').first()
    assert user is not None
    assert user.name == 'New User'

def test_login_user(client, auth_user):
    """Test user login"""
    response = client.post('/api/auth/login', json={
        'email': 'test@example.com',
        'password': 'testpass123'
    })
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert 'access_token' in data['data']
    assert 'refresh_token' in data['data']

def test_login_invalid_credentials(client):
    """Test login with invalid credentials"""
    response = client.post('/api/auth/login', json={
        'email': 'invalid@example.com',
        'password': 'wrongpassword'
    })
    
    assert response.status_code == 401
    data = response.get_json()
    assert data['status'] == 'error'

def test_get_current_user(client, auth_headers):
    """Test getting current user"""
    response = client.get('/api/auth/me', headers=auth_headers)
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert 'user' in data['data']
    assert data['data']['user']['email'] == 'test@example.com'

def test_register_duplicate_email(client, auth_user):
    """Test registering with duplicate email"""
    response = client.post('/api/auth/register', json={
        'email': 'test@example.com',
        'name': 'Another User',
        'password': 'Password123!'
    })
    
    assert response.status_code == 409
    data = response.get_json()
    assert data['status'] == 'error'
    assert 'already exists' in data['message']

def test_register_weak_password(client):
    """Test registering with weak password"""
    response = client.post('/api/auth/register', json={
        'email': 'weakpass@example.com',
        'name': 'Weak Password User',
        'password': 'weak'
    })
    
    assert response.status_code == 400
    data = response.get_json()
    assert data['status'] == 'error'
    assert 'Password must' in data['message']

def test_register_invalid_email(client):
    """Test registering with invalid email"""
    response = client.post('/api/auth/register', json={
        'email': 'invalid-email',
        'name': 'Invalid Email User',
        'password': 'Password123!'
    })
    
    assert response.status_code == 400
    data = response.get_json()
    assert data['status'] == 'error'
    assert 'Invalid email' in data['message']