import pytest
from app.models.space import Space
from app import db

def test_get_spaces(client, sample_space):
    """Test getting list of spaces"""
    response = client.get('/api/spaces')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert 'spaces' in data['data']
    assert len(data['data']['spaces']) == 1
    assert data['data']['spaces'][0]['title'] == 'Test Space'

def test_get_space_details(client, sample_space):
    """Test getting space details"""
    response = client.get(f'/api/spaces/{sample_space.id}')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert 'space' in data['data']
    assert data['data']['space']['title'] == 'Test Space'

def test_get_nonexistent_space(client):
    """Test getting non-existent space"""
    response = client.get('/api/spaces/999')
    
    assert response.status_code == 404
    data = response.get_json()
    assert data['status'] == 'error'

def test_create_space_unauthorized(client):
    """Test creating space without authentication"""
    response = client.post('/api/spaces', json={
        'title': 'New Space',
        'description': 'A new space',
        'category': 'meeting_room',
        'hourly_rate': 50.0,
        'capacity': 10,
        'address': '123 New St'
    })
    
    assert response.status_code == 401

def test_create_space_non_owner(client, auth_headers):
    """Test creating space as non-owner"""
    response = client.post('/api/spaces', json={
        'title': 'New Space',
        'description': 'A new space',
        'category': 'meeting_room',
        'hourly_rate': 50.0,
        'capacity': 10,
        'address': '123 New St'
    }, headers=auth_headers)
    
    assert response.status_code == 403

def test_search_spaces(client, sample_space):
    """Test searching spaces"""
    response = client.get('/api/spaces?query=Test')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert len(data['data']['spaces']) == 1

def test_filter_spaces_by_category(client, sample_space):
    """Test filtering spaces by category"""
    response = client.get('/api/spaces?category=meeting_room')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert len(data['data']['spaces']) == 1

def test_filter_spaces_by_price(client, sample_space):
    """Test filtering spaces by price"""
    response = client.get('/api/spaces?min_price=40&max_price=60')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert len(data['data']['spaces']) == 1

def test_filter_spaces_by_capacity(client, sample_space):
    """Test filtering spaces by capacity"""
    response = client.get('/api/spaces?capacity=5')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert len(data['data']['spaces']) == 1

def test_get_space_categories(client):
    """Test getting space categories"""
    response = client.get('/api/spaces/categories')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert 'categories' in data['data']
    assert len(data['data']['categories']) > 0

def test_get_featured_spaces(client):
    """Test getting featured spaces"""
    response = client.get('/api/spaces/featured')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert 'spaces' in data['data']